"""Publicación y consumo de eventos de llamada sobre Redis Streams."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from datetime import timedelta

from cea_contracts.events import BaseEvent, Event
from pydantic import TypeAdapter
from redis.asyncio import Redis

log = logging.getLogger("cea.bus")

_ADAPTADOR: TypeAdapter = TypeAdapter(Event)

# Cuánto sobrevive el stream de una llamada tras el último evento.
#
# Es una red de seguridad para desarrollo, no la política de retención: lo que
# debe perdurar se persiste en `call_events`, que es la fuente de verdad
# auditable. Redis aquí es transporte con memoria corta.
TTL_STREAM = timedelta(hours=6)

# Tope de eventos por llamada en Redis.
#
# Una llamada de veinte minutos con parciales a varios por segundo ronda los
# pocos miles. El límite evita que una llamada colgada por un fallo consuma
# memoria sin control.
MAX_EVENTOS = 20_000


def clave_de_stream(call_id: str) -> str:
    return f"cea:call:{call_id}"


# Cuánto bloquea cada lectura esperando eventos nuevos.
#
# Marca el ritmo del latido del WebSocket: cada vez que expira sin novedades,
# quien consume recupera el control y puede comprobar que el cliente sigue ahí.
BLOQUEO_POR_DEFECTO_MS = 15_000

# Margen del socket sobre ese bloqueo.
#
# `XREAD BLOCK n` deja la conexión esperando hasta n milisegundos, pero el
# cliente de Redis impone su propio tiempo de lectura. Si el del socket es
# menor, la conexión se corta ANTES de que Redis conteste y la suscripción
# muere con un TimeoutError en cada ciclo: el portal se desconecta solo cada
# pocos segundos y muestra "Reconectando…" sin que nada esté realmente mal.
MARGEN_SOCKET_S = 5


class EventBus:
    """Publica y consume eventos tipados de una llamada."""

    def __init__(self, redis: Redis, *, bloqueo_ms: int = BLOQUEO_POR_DEFECTO_MS) -> None:
        self._redis = redis
        self._bloqueo_ms = bloqueo_ms

    @classmethod
    def desde_url(cls, url: str, *, bloqueo_ms: int = BLOQUEO_POR_DEFECTO_MS) -> EventBus:
        redis = Redis.from_url(
            url,
            decode_responses=True,
            socket_timeout=bloqueo_ms / 1000 + MARGEN_SOCKET_S,
            socket_keepalive=True,
        )
        return cls(redis, bloqueo_ms=bloqueo_ms)

    async def aclose(self) -> None:
        await self._redis.aclose()

    async def publish(self, evento: BaseEvent) -> str:
        """Publica un evento y devuelve su identificador en el stream."""
        clave = clave_de_stream(evento.call_id)
        ident = await self._redis.xadd(
            clave,
            {"payload": evento.model_dump_json()},
            maxlen=MAX_EVENTOS,
            approximate=True,
        )
        await self._redis.expire(clave, int(TTL_STREAM.total_seconds()))
        return ident

    async def history(self, call_id: str, *, limite: int = 5_000) -> list[tuple[str, BaseEvent]]:
        """Todo lo publicado hasta ahora, en orden.

        Es lo que permite que recargar el portal a mitad de llamada devuelva la
        conversación completa y no una pantalla en blanco.
        """
        crudos = await self._redis.xrange(clave_de_stream(call_id), count=limite)
        return [(i, _ADAPTADOR.validate_json(c["payload"])) for i, c in crudos]

    async def subscribe(
        self, call_id: str, *, desde: str = "$", bloqueo_ms: int | None = None
    ) -> AsyncIterator[tuple[str, BaseEvent]]:
        """Eventos nuevos según se publican.

        `desde="$"` entrega sólo lo posterior a la suscripción; `desde="0"`
        arranca desde el principio del stream, que es lo que usa una reconexión
        para recuperar lo que se perdió.
        """
        clave = clave_de_stream(call_id)
        espera = self._bloqueo_ms if bloqueo_ms is None else bloqueo_ms
        if espera / 1000 >= self._bloqueo_ms / 1000 + MARGEN_SOCKET_S:
            raise ValueError(
                f"Bloqueo de {espera} ms por encima del tiempo de socket configurado. "
                "Construir el bus con ese mismo bloqueo para que el socket lo acompañe."
            )
        ultimo = desde
        while True:
            respuesta = await self._redis.xread({clave: ultimo}, count=200, block=espera)
            if not respuesta:
                # Tiempo agotado sin eventos: se devuelve el control para que
                # quien consume pueda enviar un latido y detectar que el
                # cliente se fue, en vez de quedarse bloqueado para siempre.
                yield ("", None)  # type: ignore[misc]
                continue
            for _clave, entradas in respuesta:
                for ident, campos in entradas:
                    ultimo = ident
                    try:
                        yield (ident, _ADAPTADOR.validate_json(campos["payload"]))
                    except Exception:  # noqa: BLE001
                        # Un evento corrupto no puede tumbar el stream entero de
                        # una llamada en curso: se registra y se sigue.
                        log.exception("Evento ilegible en %s (%s)", clave, ident)
