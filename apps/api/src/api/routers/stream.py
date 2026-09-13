"""Gateway WebSocket: retransmite los eventos de una llamada al portal."""

from __future__ import annotations

import asyncio
import logging

from cea_bus import EventBus
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from ..auth import AgentIdentity, get_auth_provider
from ..config import get_settings

log = logging.getLogger("cea.stream")

router = APIRouter(tags=["streaming"])

# Subprotocolo con el que el navegador manda el token.
#
# La API de WebSocket del navegador no permite enviar cabeceras, así que la
# alternativa habitual es meter el token en la URL. Se evita a propósito: las
# URLs acaban en los logs de acceso del servidor, en los del proxy y en el
# historial del navegador, y un token de nueve horas ahí es una credencial
# filtrada. El campo de subprotocolos sí viaja en una cabecera.
PREFIJO_TOKEN = "bearer."
SUBPROTOCOLO = "cea.v1"

# Latido. Un WebSocket puede quedar medio abierto sin que ninguno de los dos
# extremos se entere: el proceso sigue vivo, el socket parece bueno y los
# eventos se escriben a la nada. El latido lo detecta.
LATIDO_S = 20


async def _autenticar(websocket: WebSocket) -> AgentIdentity | None:
    protocolos = [p.strip() for p in websocket.headers.get("sec-websocket-protocol", "").split(",")]
    token = next((p[len(PREFIJO_TOKEN) :] for p in protocolos if p.startswith(PREFIJO_TOKEN)), None)
    if not token:
        return None
    try:
        return await get_auth_provider().verify_token(token)
    except Exception:  # noqa: BLE001 - cualquier fallo aquí es "no autenticado"
        return None


@router.websocket("/ws/calls/{call_id}")
async def stream_llamada(websocket: WebSocket, call_id: str) -> None:
    """Transcripción y eventos de la llamada, en vivo.

    Al conectar se envía primero TODO el historial y después lo nuevo. Es lo
    que hace que recargar el portal a mitad de llamada devuelva la conversación
    completa en lugar de un panel en blanco con lo que ocurra a partir de ese
    segundo.
    """
    agente = await _autenticar(websocket)
    if agente is None:
        # Se rechaza antes del handshake: aceptar y luego cerrar dejaría al
        # cliente creyendo por un instante que la sesión sirve.
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="No autenticado")
        return

    await websocket.accept(subprotocol=SUBPROTOCOLO)
    # El bus se construye con el mismo bloqueo que usará la suscripción, para
    # que el tiempo de socket lo acompañe.
    bus = EventBus.desde_url(get_settings().redis_url, bloqueo_ms=LATIDO_S * 1000)
    log.info("Portal conectado a %s (%s)", call_id, agente.username)

    try:
        ultimo = "0"
        for ident, evento in await bus.history(call_id):
            ultimo = ident
            await websocket.send_text(evento.model_dump_json())
        await websocket.send_json({"type": "stream.ready", "call_id": call_id})

        suscripcion = bus.subscribe(call_id, desde=ultimo)
        async for _ident, evento in suscripcion:
            if evento is None:
                await websocket.send_json({"type": "stream.heartbeat"})
                continue
            await websocket.send_text(evento.model_dump_json())

    except WebSocketDisconnect:
        log.info("Portal desconectado de %s", call_id)
    except asyncio.CancelledError:
        raise
    except Exception:  # noqa: BLE001
        log.exception("Fallo en el stream de %s", call_id)
    finally:
        await bus.aclose()
