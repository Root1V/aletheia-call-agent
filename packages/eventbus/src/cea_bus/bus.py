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


# Índice de llamadas abiertas.
#
# Los eventos viven en un stream por llamada, que es lo correcto para el portal
# —cada pestaña sigue una sola— pero deja sin respuesta la pregunta del
# orquestador: "¿qué llamadas hay?". Sin este índice tendría que sondear las
# claves de Redis con SCAN, que es exactamente lo que Redis pide no hacer.
CLAVE_DIRECTORIO = "cea:calls"
MAX_LLAMADAS = 1_000


def clave_de_contexto(call_id: str) -> str:
    return f"cea:context:{call_id}"


def clave_de_seq(call_id: str) -> str:
    return f"cea:seq:{call_id}"


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
        """Publica un evento y devuelve su identificador en el stream.

        El `seq` lo asigna aquí un contador atómico de la llamada, y se ignora
        el que traiga el evento. Una llamada tiene más de un escritor —el worker
        transcribe mientras el orquestador sugiere— y dos contadores en dos
        procesos acaban dando el mismo número a eventos distintos: el replay
        deja de ser reproducible y el portal ordena mal.
        """
        clave = clave_de_stream(evento.call_id)
        evento = evento.model_copy(
            update={"seq": await self._redis.incr(clave_de_seq(evento.call_id))}
        )
        ident = await self._redis.xadd(
            clave,
            {"payload": evento.model_dump_json()},
            maxlen=MAX_EVENTOS,
            approximate=True,
        )
        await self._redis.expire(clave, int(TTL_STREAM.total_seconds()))

        # El inicio de llamada se anota además en el índice, para que quien
        # consume sepa que hay una llamada nueva sin sondear.
        if evento.type == "call.started":
            await self._redis.xadd(
                CLAVE_DIRECTORIO,
                {"call_id": evento.call_id},
                maxlen=MAX_LLAMADAS,
                approximate=True,
            )
            await self._redis.expire(CLAVE_DIRECTORIO, int(TTL_STREAM.total_seconds()))
        return ident

    async def guardar_contexto(self, evento: BaseEvent) -> str:
        """Publica el contexto y además lo guarda fuera del stream.

        El contexto se calcula ANTES de descolgar, y `reset()` vacía el stream
        al empezar la llamada: publicado sólo como evento, el pre-pop se borra
        justo cuando el copiloto va a necesitarlo y las sugerencias salen sin
        saber de qué cargo se está hablando.

        Guardarlo aparte lo reconoce por lo que es: estado de la llamada, no un
        hecho ocurrido durante ella. Sigue yendo al stream para que el portal lo
        reciba en vivo.
        """
        await self._redis.set(
            clave_de_contexto(evento.call_id),
            evento.model_dump_json(),
            ex=int(TTL_STREAM.total_seconds()),
        )
        return await self.publish(evento)

    async def contexto(self, call_id: str) -> BaseEvent | None:
        """El último contexto guardado de la llamada, o None si no hay."""
        crudo = await self._redis.get(clave_de_contexto(call_id))
        return _ADAPTADOR.validate_json(crudo) if crudo else None

    async def reset(self, call_id: str) -> None:
        """Borra el historial de una llamada.

        Una llamada nueva es una llamada nueva. Sin esto, reproducir dos veces
        el mismo escenario apila los eventos de ambas en el mismo stream, y
        como el número de secuencia reinicia en cada ejecución, el portal los
        ordena intercalados y muestra cada turno por duplicado.
        """
        await self._redis.delete(clave_de_stream(call_id), clave_de_seq(call_id))

    async def llamadas(
        self, *, desde: str = "$", bloqueo_ms: int | None = None
    ) -> AsyncIterator[tuple[str, str]]:
        """Identificadores de las llamadas según empiezan.

        `desde="0"` recorre primero las que ya estaban en curso: un orquestador
        que se reinicia a mitad de una llamada debe volver a engancharse a ella,
        no esperar a la siguiente.
        """
        espera = self._bloqueo_ms if bloqueo_ms is None else bloqueo_ms
        ultimo = desde
        while True:
            respuesta = await self._redis.xread({CLAVE_DIRECTORIO: ultimo}, count=100, block=espera)
            if not respuesta:
                continue
            for _clave, entradas in respuesta:
                for ident, campos in entradas:
                    ultimo = ident
                    yield (ident, campos["call_id"])

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
