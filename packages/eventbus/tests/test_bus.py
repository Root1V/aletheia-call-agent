"""Tests del bus de eventos."""

from __future__ import annotations

import asyncio
import os
import uuid

import pytest
from cea_bus import EventBus
from cea_bus.bus import MARGEN_SOCKET_S
from cea_contracts import AsrFinal, AsrPartial, CallEnded, Speaker
from redis.asyncio import Redis

REDIS_URL = os.environ.get("CEA_REDIS_URL", "redis://localhost:6380/0")


async def _hay_redis() -> bool:
    try:
        r = Redis.from_url(REDIS_URL, socket_connect_timeout=1)
        await r.ping()
        await r.aclose()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not asyncio.run(_hay_redis()), reason="Sin Redis. Levantar con `make up`."
)


@pytest.fixture
async def bus():
    b = EventBus.desde_url(REDIS_URL, bloqueo_ms=500)
    yield b
    await b.aclose()


@pytest.fixture
def call_id() -> str:
    return f"test-{uuid.uuid4().hex[:8]}"


async def test_lo_publicado_se_recupera_con_su_tipo(bus, call_id) -> None:
    """El bus devuelve el evento concreto, no un diccionario.

    Es lo que permite que quien consume trabaje con tipos en vez de adivinar
    campos, y que un evento mal formado falle al entrar y no tres capas después.
    """
    await bus.publish(
        AsrFinal(
            call_id=call_id,
            speaker=Speaker.CUSTOMER,
            turn_id="t1",
            text="no reconozco este cargo",
            started_at_ms=0,
            ended_at_ms=1500,
        )
    )

    historial = await bus.history(call_id)

    assert len(historial) == 1
    _, evento = historial[0]
    assert isinstance(evento, AsrFinal)
    assert evento.text == "no reconozco este cargo"
    assert evento.speaker is Speaker.CUSTOMER


async def test_el_historial_sobrevive_a_la_reconexion(bus, call_id) -> None:
    """Redis Streams y no pub/sub, precisamente por esto.

    Un ejecutivo que recarga el portal a mitad de llamada tiene que recuperar
    la conversación entera. Con pub/sub, lo emitido antes de suscribirse
    simplemente no existe y el panel aparecería en blanco.
    """
    for i in range(5):
        await bus.publish(
            AsrPartial(
                call_id=call_id,
                seq=i,
                speaker=Speaker.CUSTOMER,
                turn_id="t1",
                text=f"hipótesis {i}",
                started_at_ms=0,
            )
        )

    # Un consumidor que llega tarde.
    otro = EventBus.desde_url(REDIS_URL, bloqueo_ms=500)
    try:
        assert len(await otro.history(call_id)) == 5
    finally:
        await otro.aclose()


async def test_la_suscripcion_entrega_lo_nuevo(bus, call_id) -> None:
    recibidos = []

    async def consumir():
        async for _ident, evento in bus.subscribe(call_id, desde="0"):
            if evento is None:
                continue
            recibidos.append(evento)
            if isinstance(evento, CallEnded):
                return

    tarea = asyncio.create_task(consumir())
    await asyncio.sleep(0.1)
    await bus.publish(
        AsrFinal(
            call_id=call_id,
            speaker=Speaker.AGENT,
            turn_id="t1",
            text="con gusto lo revisamos",
            started_at_ms=0,
            ended_at_ms=900,
        )
    )
    await bus.publish(CallEnded(call_id=call_id, duration_ms=1000))
    await asyncio.wait_for(tarea, timeout=5)

    assert len(recibidos) == 2
    assert isinstance(recibidos[-1], CallEnded)


async def test_el_bloqueo_no_puede_superar_el_tiempo_de_socket(bus, call_id) -> None:
    """`XREAD BLOCK n` con un socket que expira antes mata la suscripción.

    El síntoma no es un error visible: el portal se desconecta solo cada pocos
    segundos y muestra "Reconectando…" mientras todo lo demás funciona. Mejor
    rechazarlo al configurarlo que depurarlo desde la interfaz.
    """
    with pytest.raises(ValueError, match="tiempo de socket"):
        exagerado = int((0.5 + MARGEN_SOCKET_S) * 1000) + 1000
        async for _ in bus.subscribe(call_id, bloqueo_ms=exagerado):
            break


async def test_un_evento_ilegible_no_tumba_el_stream(bus, call_id) -> None:
    """Una llamada en curso no puede caerse por un evento corrupto."""
    from cea_bus import clave_de_stream

    redis = Redis.from_url(REDIS_URL, decode_responses=True)
    try:
        await redis.xadd(clave_de_stream(call_id), {"payload": "{esto no es json válido"})
        await bus.publish(CallEnded(call_id=call_id, duration_ms=1))
    finally:
        await redis.aclose()

    recibidos = []

    async def consumir():
        async for _ident, evento in bus.subscribe(call_id, desde="0"):
            if evento is None:
                continue
            recibidos.append(evento)
            return

    await asyncio.wait_for(asyncio.create_task(consumir()), timeout=5)
    assert isinstance(recibidos[0], CallEnded)


async def test_reset_deja_la_llamada_en_limpio(bus, call_id) -> None:
    """Una llamada nueva es una llamada nueva.

    Los identificadores de llamada de los escenarios son deterministas, así que
    sin esto reproducir dos veces el mismo guion apila los eventos de ambas
    ejecuciones en el mismo stream.
    """
    await bus.publish(CallEnded(call_id=call_id, duration_ms=1))
    assert len(await bus.history(call_id)) == 1

    await bus.reset(call_id)

    assert await bus.history(call_id) == []


async def test_dos_escritores_no_repiten_el_numero_de_secuencia(bus, call_id) -> None:
    """Una llamada tiene más de un escritor, y el `seq` tiene que seguir sirviendo.

    El worker transcribe mientras el orquestador publica sugerencias sobre la
    misma llamada. Cuando cada proceso llevaba su propio contador, los dos
    numeraban desde el mismo sitio: dos eventos distintos con el mismo `seq`.

    Se comprueba la UNICIDAD, no que el orden del stream siga al del `seq`.
    Reservar el número y escribir son dos comandos, así que dos escritores
    concurrentes pueden invertir un par, y esta misma prueba lo pilló afirmando
    de más. El orden lo da el stream; `seq` identifica.
    """
    otro = EventBus.desde_url(REDIS_URL, bloqueo_ms=500)
    try:

        async def publicar(b: EventBus, veces: int) -> None:
            for _ in range(veces):
                await b.publish(
                    AsrPartial(
                        call_id=call_id,
                        # Deliberadamente el mismo seq en todos: lo que el
                        # publicador diga se ignora.
                        seq=1,
                        speaker=Speaker.CUSTOMER,
                        turn_id="t1",
                        text="hipótesis",
                        started_at_ms=0,
                    )
                )

        await asyncio.gather(publicar(bus, 25), publicar(otro, 25))
    finally:
        await otro.aclose()

    secuencias = [e.seq for _i, e in await bus.history(call_id)]

    assert len(secuencias) == 50
    assert len(set(secuencias)) == 50, "hay números de secuencia repetidos"
    assert sorted(secuencias) == list(range(1, 51)), "la numeración tiene huecos o saltos"


async def test_el_reset_devuelve_la_numeracion_al_principio(bus, call_id) -> None:
    """Reproducir un escenario dos veces tiene que numerar igual las dos veces.

    Si el contador sobreviviera al reset, la segunda reproducción del mismo
    guion produciría eventos idénticos con `seq` distinto, y las comparaciones
    de las evaluaciones deterministas fallarían sin que nada estuviera mal.
    """
    await bus.publish(CallEnded(call_id=call_id, duration_ms=1))
    await bus.publish(CallEnded(call_id=call_id, duration_ms=2))
    await bus.reset(call_id)
    await bus.publish(CallEnded(call_id=call_id, duration_ms=3))

    _ident, evento = (await bus.history(call_id))[0]
    assert evento.seq == 1


async def test_el_contexto_sobrevive_al_reset(bus, call_id) -> None:
    """El pre-pop se calcula ANTES de descolgar y el worker vacía el stream al empezar.

    Guardado sólo como evento, el contexto se borraba justo cuando el copiloto
    iba a necesitarlo, y las sugerencias salían sin saber de qué cargo se estaba
    hablando. El síntoma no era un error: eran sugerencias genéricas.
    """
    from cea_contracts import CallIntent, ContextEnriched, IntentPrediction

    contexto = _contexto_minimo(call_id)
    await bus.guardar_contexto(ContextEnriched(call_id=call_id, context=contexto))

    # También llegó al stream, que es como lo recibe el portal en vivo.
    assert any(e.type == "context.enriched" for _i, e in await bus.history(call_id))

    await bus.reset(call_id)

    assert await bus.history(call_id) == []
    guardado = await bus.contexto(call_id)
    assert guardado is not None
    assert guardado.context.intent.intent is CallIntent.DISPUTA_CARGO_NO_RECONOCIDO
    assert isinstance(guardado.context.intent, IntentPrediction)


def _contexto_minimo(call_id: str):
    from datetime import UTC, date, datetime

    from cea_contracts import (
        AuthLevel,
        CallContext,
        CallIntent,
        Customer,
        IntentPrediction,
        TrustState,
    )

    return CallContext(
        call_id=call_id,
        customer=Customer(
            customer_id="CUS000001",
            full_name="Magaly Bardales",
            document_type="DNI",
            document_masked="***8745",
            segment="preferente",
            customer_since=date(2010, 1, 1),
        ),
        trust=TrustState(level=AuthLevel.VERIFICADO),
        intent=IntentPrediction(intent=CallIntent.DISPUTA_CARGO_NO_RECONOCIDO, confidence=0.9),
        generated_at=datetime.now(UTC),
    )


async def test_un_evento_ilegible_no_deja_el_historial_en_blanco(bus, call_id) -> None:
    """La suscripción ya se protegía de esto; el historial no.

    Se notó con un cambio de contrato: un proceso con la versión anterior no
    sabía leer un campo nuevo, `history()` lanzaba, y el portal mostraba "sin
    conexión con el servidor de la llamada" sobre una conversación que estaba
    entera en Redis. Perder un evento es aceptable; perder la llamada no.
    """
    from cea_bus import clave_de_stream

    await bus.publish(
        AsrFinal(
            call_id=call_id,
            speaker=Speaker.CUSTOMER,
            turn_id="t1",
            text="no reconozco este cargo",
            started_at_ms=0,
            ended_at_ms=900,
        )
    )
    redis = Redis.from_url(REDIS_URL, decode_responses=True)
    try:
        # Un evento con un campo que esta versión no sabe validar.
        await redis.xadd(
            clave_de_stream(call_id),
            {"payload": '{"type":"case.classified","call_id":"x","proposed_type":"inventado"}'},
        )
    finally:
        await redis.aclose()
    await bus.publish(CallEnded(call_id=call_id, duration_ms=1000))

    historial = await bus.history(call_id)

    tipos = [e.type for _i, e in historial]
    assert tipos == ["asr.final", "call.ended"], "se perdieron eventos legibles por uno corrupto"
