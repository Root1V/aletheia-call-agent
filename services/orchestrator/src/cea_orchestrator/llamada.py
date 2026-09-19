"""Atención de una llamada: escuchar el bus, decidir, sugerir.

Un objeto por llamada. Consume el mismo stream que el portal —no un canal
privilegiado— y publica de vuelta en él. Esa simetría es lo que hace que una
llamada grabada se pueda reproducir contra el orquestador y produzca las mismas
sugerencias: es la base de las evaluaciones deterministas.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid

from axonium.errors import RateLimitError
from cea_bus import EventBus
from cea_contracts import (
    BaseEvent,
    CallContext,
    EmotionLabel,
    Speaker,
    SuggestionCompleted,
    SuggestionStarted,
)
from cea_copilot import generar, instruccion, resumir
from cea_llm import AxoniumProvider
from cea_rag import Pasaje, embeber_consulta, reordenar
from psycopg_pool import AsyncConnectionPool

from .politica import Politica

log = logging.getLogger("cea.orquestador")

# Motivo con el que se cierra una sugerencia que un turno posterior dejó
# obsoleta. Se publica en lugar de callar: el portal ya mostró la tarjeta
# "redactando" al recibir `suggestion.started`, y sin este cierre se quedaría
# girando para siempre.
SUPERADA = "El cliente siguió hablando; esta respuesta ya no venía al caso."

# Qué se le dice al ejecutivo cuando falla la plataforma de modelos.
#
# No el mensaje de la excepción: lleva identificadores de petición y nombres de
# endpoint que no significan nada en una silla de atención al cliente, y que
# además no debería estar leyendo mientras habla con alguien.
FALLO_DE_PLATAFORMA = "El servicio de modelos no respondió a tiempo. Continúe usted."
SIN_CUPO = "El servicio de modelos está saturado ahora mismo. Continúe usted."


def _motivo_legible(error: Exception) -> str:
    """Traduce el fallo a algo accionable por quien está al teléfono."""
    if isinstance(error, RateLimitError):
        return SIN_CUPO
    return FALLO_DE_PLATAFORMA


class Llamada:
    """Estado y decisiones del copiloto durante una llamada."""

    def __init__(
        self,
        call_id: str,
        *,
        bus: EventBus,
        pool: AsyncConnectionPool,
        proveedor: AxoniumProvider,
        reordenar_pasajes: bool = True,
    ) -> None:
        self._call_id = call_id
        self._bus = bus
        self._pool = pool
        self._proveedor = proveedor
        self._reordenar = reordenar_pasajes

        self._politica = Politica()
        self._contexto: CallContext | None = None
        self._emocion: dict[EmotionLabel, float] | None = None
        self._textos: dict[str, tuple[Speaker, str]] = {}
        self._en_curso: asyncio.Task | None = None
        self._id_en_curso: str | None = None

    # ── ciclo de vida ────────────────────────────────────────────────────────

    async def atender(self) -> None:
        """Recorre el historial sin disparar y luego sigue la llamada en vivo.

        La primera pasada NO genera sugerencias. Un orquestador que arranca a
        mitad de llamada —o que se reinicia— encontraría en el historial todos
        los turnos ya dichos y produciría una ráfaga de tarjetas sobre
        conversación pasada, que es la peor forma posible de volver.
        """
        # El contexto se lee del estado de la llamada y no del stream: el
        # pre-pop se calcula antes de descolgar, y el worker vacía el stream al
        # empezar. Buscarlo sólo en el historial lo encontraría vacío siempre.
        guardado = await self._bus.contexto(self._call_id)
        if guardado is not None:
            self._registrar(guardado)

        ultimo = "0"
        for ident, evento in await self._bus.history(self._call_id):
            ultimo = ident
            self._registrar(evento)

        log.info(
            "Atendiendo %s (contexto: %s, historial: %d turnos)",
            self._call_id,
            "sí" if self._contexto else "no",
            len(self._textos),
        )

        async for _ident, evento in self._bus.subscribe(self._call_id, desde=ultimo):
            if evento is None:
                continue
            self._registrar(evento)

            if evento.type == "call.ended":
                break
            if evento.type == "turn.ended":
                await self._considerar(evento.turn_id)

        await self._cancelar_en_curso()
        log.info("Llamada %s terminada", self._call_id)

    def _registrar(self, evento: BaseEvent) -> None:
        """Actualiza el estado con un evento, sin decidir nada."""
        if evento.type == "context.enriched":
            self._contexto = evento.context
        elif evento.type == "emotion.frame":
            self._emocion = evento.scores
        elif evento.type == "asr.final":
            self._textos[evento.turn_id] = (evento.speaker, evento.text)

    # ── decisión ─────────────────────────────────────────────────────────────

    async def _considerar(self, turn_id: str) -> None:
        registro = self._textos.get(turn_id)
        if registro is None:
            # El final de turno llegó sin su texto. Ocurre con un turno
            # compuesto sólo de puntuación, que el reconocedor descarta.
            return
        speaker, texto = registro

        motivo = self._politica.evaluar(speaker, texto)
        if motivo is not None:
            log.debug("Sin sugerencia en %s: %s", turn_id, motivo)
            return

        # Un turno nuevo invalida la generación anterior. Se cancela ANTES de
        # empezar la siguiente para no tener dos escribiendo en el mismo panel.
        await self._cancelar_en_curso(motivo=SUPERADA)

        self._politica.anotar_emision()
        self._id_en_curso = f"sug-{uuid.uuid4().hex[:10]}"
        self._en_curso = asyncio.create_task(self._sugerir(self._id_en_curso, turn_id, texto))

    async def _cancelar_en_curso(self, *, motivo: str | None = None) -> None:
        tarea, ident = self._en_curso, self._id_en_curso
        self._en_curso = self._id_en_curso = None
        if tarea is None or tarea.done():
            return
        tarea.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await tarea
        if motivo and ident:
            await self._publicar(
                SuggestionCompleted(
                    call_id=self._call_id,
                    suggestion_id=ident,
                    text="",
                    blocked=True,
                    blocked_reason=motivo,
                )
            )

    # ── generación ───────────────────────────────────────────────────────────

    async def _sugerir(self, suggestion_id: str, turn_id: str, texto: str) -> None:
        """Genera y publica. Se ejecuta como tarea, y puede ser cancelada."""
        await self._publicar(
            SuggestionStarted(
                call_id=self._call_id,
                suggestion_id=suggestion_id,
                trigger_turn_id=turn_id,
            )
        )

        tono, etiqueta = instruccion(self._emocion)
        consulta = self._consulta(texto)

        # Sin vector la búsqueda sigue por la mitad léxica: `embeddings` y
        # `rerank` comparten cupo y `chat` tiene el suyo, así que quedarse sin
        # el uno no deja sin sugerencia. La degradación la decide `cea_rag`,
        # que es quien sabe qué pierde la búsqueda al faltarle el vector.
        vector = await embeber_consulta(self._proveedor, consulta)

        try:
            async with self._pool.connection() as conn, conn.cursor() as cur:
                sugerencia = await generar(
                    cur,
                    self._proveedor,
                    turno_del_cliente=texto,
                    datos_de_la_llamada=resumir(self._contexto) if self._contexto else "",
                    consulta_kb=consulta,
                    vector=vector,
                    tono=tono,
                    reordenador=self._reordenador if self._reordenar else None,
                )
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            # Un fallo de la plataforma tiene que CERRAR la tarjeta, no dejarla
            # girando. Sin esto, la excepción muere dentro de la tarea, el
            # `suggestion.completed` no se publica nunca y el portal se queda
            # con el "redactando…" para siempre: el ejecutivo no sabe si debe
            # seguir esperando o hablar.
            log.exception("La generación falló en %s", self._call_id)
            await self._publicar(
                SuggestionCompleted(
                    call_id=self._call_id,
                    suggestion_id=suggestion_id,
                    text="",
                    blocked=True,
                    blocked_reason=_motivo_legible(e),
                )
            )
            return

        # El texto sólo se publica si pasó los guardarraíles.
        #
        # Por eso tampoco se retransmiten los tokens según se generan: la
        # verificación de cifras ocurre sobre el texto completo, y una comisión
        # equivocada que parpadeó medio segundo en pantalla ya la puede haber
        # leído el ejecutivo en voz alta. Se gana latencia percibida con
        # `suggestion.started`, no arriesgando el número.
        await self._publicar(
            SuggestionCompleted(
                call_id=self._call_id,
                suggestion_id=suggestion_id,
                text=sugerencia.texto if sugerencia.mostrable else "",
                citations=sugerencia.citas if sugerencia.mostrable else (),
                emotion_adapted_to=etiqueta,
                blocked=not sugerencia.mostrable,
                blocked_reason=sugerencia.guardarrailes.motivo,
                latency_ms=int(sugerencia.latencia_ms),
            )
        )
        log.info(
            "Sugerencia %s en %s: %s (%.0f ms, ttft %.0f ms)",
            suggestion_id,
            self._call_id,
            "mostrable"
            if sugerencia.mostrable
            else f"bloqueada: {sugerencia.guardarrailes.motivo}",
            sugerencia.latencia_ms,
            sugerencia.ttft_ms,
        )

    async def _reordenador(self, consulta: str, pasajes: list[Pasaje], cuantos: int):
        return await reordenar(self._proveedor, consulta, pasajes, devolver=cuantos)

    def _consulta(self, texto: str) -> str:
        """Consulta a la base de conocimiento: el turno del cliente, tal cual.

        Aquí estuvo antepuesta la intención predicha, con el razonamiento de que
        un turno vago como "¿y esto qué es?" no recupera nada por sí solo. La
        medición lo desmintió: sobre el conjunto de evaluación el prefijo baja
        el acierto en primera posición del 85% al 54% y la cobertura del 92% al
        77%. Arrastra TODA consulta hacia los documentos de la intención, de modo
        que un cliente que en mitad de una disputa pregunta cuánto cuesta
        reponer el plástico recibe el procedimiento de disputas.

        El caso que el prefijo quería rescatar apenas llega hasta aquí: la
        política no genera sugerencia para turnos de menos de cinco palabras, que
        es donde caen los turnos demasiado vagos para recuperar nada.
        """
        return texto

    async def _publicar(self, evento: BaseEvent) -> None:
        await self._bus.publish(evento)
