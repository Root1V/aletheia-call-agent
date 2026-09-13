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
