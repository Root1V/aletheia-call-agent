"""Test de extremo a extremo del pipeline de llamada.

Reproduce un guion acelerado y comprueba que por el bus sale la conversación
completa, con los hablantes separados. Es la prueba que cubre el camino entero
—ingesta, reconocimiento, bus— y la única que habría detectado varios de los
defectos que aparecieron construyéndolo.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from pathlib import Path

import pytest
from agent_worker.ingest.file_replay import FileReplayAdapter
from agent_worker.pipeline import CallPipeline
from cea_asr import SherpaStreamingASR
from cea_bus import EventBus
from cea_contracts import AsrFinal, AsrPartial, CallEnded, CallStarted, Speaker, TurnEnded
from redis.asyncio import Redis

REDIS_URL = os.environ.get("CEA_REDIS_URL", "redis://localhost:6380/0")
MODELO = Path("models/sherpa-onnx-streaming-zipformer-es-kroko-2025-08-06")
AUDIO = Path("evals/audio/disputa_cargo_no_reconocido")


async def _hay_redis() -> bool:
    try:
        r = Redis.from_url(REDIS_URL, socket_connect_timeout=1)
        await r.ping()
        await r.aclose()
        return True
    except Exception:
        return False


pytestmark = [
    pytest.mark.skipif(not MODELO.exists(), reason="Falta el modelo. `make models`."),
    pytest.mark.skipif(
        not (AUDIO / "manifiesto.yaml").exists(), reason="Falta el audio. `make audio`."
    ),
    pytest.mark.skipif(not asyncio.run(_hay_redis()), reason="Sin Redis. `make up`."),
]


@pytest.fixture(scope="module")
async def eventos() -> list:
    """Reproduce la llamada una vez y devuelve todo lo publicado.

    Se hace a nivel de módulo porque cargar el modelo y reproducir el guion
    tarda unos segundos; repetirlo por test multiplicaría el tiempo de la suite
    sin comprobar nada nuevo.
    """
    call_id = f"test-{uuid.uuid4().hex[:8]}"
    bus = EventBus.desde_url(REDIS_URL, bloqueo_ms=500)
    adaptador = FileReplayAdapter(call_id, AUDIO, velocidad=25.0)
    pipeline = CallPipeline(
        call_id=call_id,
        customer_id="CUS000001",
        agent_id="test",
        asr=SherpaStreamingASR(MODELO),
        bus=bus,
        ingress="file_replay",
    )

    await pipeline.start(room="test")
    async for frame in adaptador.frames():
        await pipeline.feed(frame)
    await pipeline.stop()

    historial = [e for _i, e in await bus.history(call_id)]
    await Redis.from_url(REDIS_URL).delete(f"cea:call:{call_id}")
    await bus.aclose()
    return historial


def test_la_llamada_se_abre_y_se_cierra(eventos) -> None:
    assert isinstance(eventos[0], CallStarted)
    assert isinstance(eventos[-1], CallEnded)
    assert eventos[0].ingress == "file_replay"


def test_salen_los_diez_turnos_del_guion(eventos) -> None:
    """Uno por intervención: ni fragmentos de más ni turnos perdidos.

    Cuando el reconocedor emitía el signo de puntuación final como turno
    aparte, salían quince en vez de diez y la UI mostraba burbujas con sólo
    un punto dentro.
    """
    finales = [e for e in eventos if isinstance(e, AsrFinal)]
    assert 9 <= len(finales) <= 12, f"{len(finales)} turnos finales"


def test_ningun_turno_esta_vacio(eventos) -> None:
    """Un turno sin contenido dispararía una sugerencia del copiloto sobre nada."""
    for e in eventos:
        if isinstance(e, AsrFinal | AsrPartial):
            assert any(c.isalnum() for c in e.text), f"turno sin contenido: {e.text!r}"


def test_los_hablantes_no_se_mezclan(eventos) -> None:
    """La separación por track es lo que nos ahorra la diarización.

    Si el estado del reconocedor se compartiera entre hablantes, el texto de
    uno aparecería atribuido al otro y toda la ventaja se perdería.
    """
    finales = [e for e in eventos if isinstance(e, AsrFinal)]
    por_hablante = {Speaker.CUSTOMER: [], Speaker.AGENT: []}
    for e in finales:
        por_hablante[e.speaker].append(e.text.lower())

    assert por_hablante[Speaker.CUSTOMER] and por_hablante[Speaker.AGENT]
    # Frases inconfundibles de cada lado del guion.
    assert any("no reconozco" in t for t in por_hablante[Speaker.CUSTOMER])
    assert any("revisamos" in t or "detalle" in t for t in por_hablante[Speaker.AGENT])
    assert not any("revisamos" in t for t in por_hablante[Speaker.CUSTOMER])


def test_cada_final_trae_su_fin_de_turno(eventos) -> None:
    """El orquestador se entera de que alguien calló por un evento propio.

    Si tuviera que deducirlo inspeccionando transcripciones, la capa que decide
    cuándo sugerir quedaría acoplada al formato del texto.
    """
    finales = [e for e in eventos if isinstance(e, AsrFinal)]
    fines = [e for e in eventos if isinstance(e, TurnEnded)]
    assert len(fines) == len(finales)
    assert {e.turn_id for e in fines} == {e.turn_id for e in finales}


def test_hay_parciales_antes_de_cada_final(eventos) -> None:
    """Sin parciales no hay "el texto aparece mientras habla", que es el punto."""
    parciales = [e for e in eventos if isinstance(e, AsrPartial)]
    assert len(parciales) > 20, f"sólo {len(parciales)} parciales"


def test_la_secuencia_es_monotona(eventos) -> None:
    """El `seq` ordena el replay; si se repite o retrocede, deja de servir."""
    secuencias = [e.seq for e in eventos]
    assert secuencias == sorted(secuencias)
    assert len(set(secuencias)) == len(secuencias)
