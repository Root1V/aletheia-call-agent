"""Contrato de eventos del copiloto.

El bus de eventos es el contrato del sistema. Esto da tres propiedades que
valen más que cualquier modelo concreto:

1. Cualquier modelo se reemplaza sin tocar la UI.
2. La llamada completa se persiste y se REPRODUCE (event sourcing), lo que hace
   posibles las evaluaciones deterministas y los tests de regresión.
3. Los servicios escalan de forma independiente.

Los `type` son cadenas estables: renombrar uno es un cambio de contrato que
rompe a los consumidores y exige migración.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from .domain import CallContext, Case, IntentPrediction
from .enums import CaseType, EmotionLabel, PIIKind, RiskSignalKind, Speaker


def _now_ms() -> int:
    return int(time.time() * 1000)


def _new_id() -> str:
    return uuid.uuid4().hex


class BaseEvent(BaseModel):
    """Campos comunes a todo evento del bus."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_id: str = Field(default_factory=_new_id)
    call_id: str
    ts_ms: int = Field(default_factory=_now_ms, description="Epoch en milisegundos.")
    seq: int = Field(
        default=0,
        description=(
            "Identificador correlativo dentro de la llamada. Lo asigna el BUS al "
            "publicar, no quien construye el evento: una llamada tiene más de un "
            "escritor —el worker transcribe mientras el orquestador sugiere— y dos "
            "contadores en dos procesos producen el mismo número para eventos "
            "distintos. "
            "Es ÚNICO, pero no es el orden: el orden lo da el identificador del "
            "stream, que Redis asigna de forma atómica al escribir. Reservar el "
            "número y escribir son dos operaciones, así que con dos escritores a la "
            "vez el evento que reservó el 7 puede quedar escrito antes que el del 6. "
            "Ordenar por `seq` en lugar de por llegada devolvería ese par invertido."
        ),
    )


# ──────────────────────────────────────────────────────────────────────────────
# Ciclo de vida de la llamada
# ──────────────────────────────────────────────────────────────────────────────


class CallStarted(BaseEvent):
    type: Literal["call.started"] = "call.started"
    customer_id: str
    agent_id: str
    room: str
    ingress: str = Field(
        description="livekit | audiosocket | mod_audio_fork | siprec | file_replay"
    )
    sample_rate: int = 16000


class CallEnded(BaseEvent):
    type: Literal["call.ended"] = "call.ended"
    duration_ms: int
    reason: str = "normal"


# ──────────────────────────────────────────────────────────────────────────────
# Transcripción — arquitectura de dos velocidades
# ──────────────────────────────────────────────────────────────────────────────


class AsrPartial(BaseEvent):
    """Hipótesis parcial de la vía rápida (<300 ms). Se pinta en gris y se sustituye."""

    type: Literal["asr.partial"] = "asr.partial"
    speaker: Speaker
    turn_id: str
    text: str
    started_at_ms: int


class AsrFinal(BaseEvent):
    """Texto consolidado del turno.

    Puede provenir de la vía rápida o de la re-transcripción precisa: el campo
    `reconciled` dice cuál, porque la UI reemplaza el parcial cuando llega el
    final endurecido.
    """

    type: Literal["asr.final"] = "asr.final"
    speaker: Speaker
    turn_id: str
    text: str
    started_at_ms: int
    ended_at_ms: int
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    reconciled: bool = Field(
        default=False, description="True si viene de la vía precisa y sustituye al parcial."
    )
    redactions: tuple[PIIKind, ...] = Field(
        default=(),
        description="Qué se redactó. El texto ya llega limpio: el original no existe aguas abajo.",
    )


class TurnEnded(BaseEvent):
    """Fin de turno detectado por VAD + clasificador semántico.

    Es el disparador de la sugerencia. `predicted` marca los disparos
    especulativos, que empiezan a generar antes de la certeza para ganar
    latencia.
    """

    type: Literal["turn.ended"] = "turn.ended"
    speaker: Speaker
    turn_id: str
    predicted: bool = False
    silence_ms: int = 0


# ──────────────────────────────────────────────────────────────────────────────
# Emoción — sólo del cliente, por construcción
# ──────────────────────────────────────────────────────────────────────────────


class EmotionFrame(BaseEvent):
    """Estado emocional del cliente a 2 Hz.

    RESTRICCIÓN ARQUITECTÓNICA: `speaker` es un Literal fijado a CUSTOMER, de
    modo que es imposible construir este evento para el ejecutivo. No es una
    opción de configuración que alguien pueda invertir por descuido.

    El razonamiento está en el plan (§4.3): medir emocionalmente a los empleados
    envenena la relación laboral, convierte al copiloto en herramienta de
    vigilancia a ojos del ejecutivo, y cierra la puerta a exportar el producto a
    Europa, donde el EU AI Act lo prohíbe expresamente en el ámbito laboral.
    """

    type: Literal["emotion.frame"] = "emotion.frame"
    speaker: Literal[Speaker.CUSTOMER] = Speaker.CUSTOMER

    scores: dict[EmotionLabel, float] = Field(
        description=(
            "Probabilidades CALIBRADAS y suavizadas: una barra al 80% significa 80%. "
            "El diccionario es PARCIAL a propósito — sólo lleva las dimensiones que "
            "las señales disponibles permiten sostener. Las ausentes se muestran como "
            "pendientes, no como cero."
        )
    )
    valence: float | None = Field(
        default=None,
        ge=-1.0,
        le=1.0,
        description=(
            "None cuando no se ha medido. La prosodia sola no distingue valencia: "
            "alegría y enfado comparten energía alta, tono alto y ritmo rápido. "
            "Enviar 0.0 en su lugar haría que la UI mostrara 'neutral' donde en "
            "realidad no hay dato, que es peor que no mostrar nada."
        ),
    )
    arousal: float = Field(ge=-1.0, le=1.0)
    dominance: float | None = Field(default=None, ge=-1.0, le=1.0)

    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "Calidad de la señal. Por debajo del umbral la UI pinta la banda en gris "
            "en lugar de inventar una emoción."
        ),
    )
    window_ms: int = 2500
    contributions: dict[str, float] = Field(
        default_factory=dict,
        description="Peso de cada señal en la fusión: acoustic | text | conversational.",
    )


class EscalationAlert(BaseEvent):
    """Aviso de riesgo de escalamiento por umbral sostenido, no por un pico."""

    type: Literal["emotion.escalation"] = "emotion.escalation"
    level: str = Field(description="atencion | alto | critico")
    reason: str
    sustained_ms: int


# ──────────────────────────────────────────────────────────────────────────────
# Comprensión
# ──────────────────────────────────────────────────────────────────────────────


class NluTurn(BaseEvent):
    """Intención, entidades y sentimiento textual de un turno cerrado."""

    type: Literal["nlu.turn"] = "nlu.turn"
    speaker: Speaker
    turn_id: str
    intent: str | None = None
    intent_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    entities: dict[str, str] = Field(default_factory=dict)
    sentiment: float | None = Field(default=None, ge=-1.0, le=1.0)


class RiskSignal(BaseEvent):
    """Señal textual de riesgo regulatorio o reputacional."""

    type: Literal["risk.signal"] = "risk.signal"
    kind: RiskSignalKind
    turn_id: str
    quote: str = Field(description="Fragmento que disparó la señal, ya redactado.")


class IntentPredicted(BaseEvent):
    """Predicción del motivo de la llamada. Reconfigura el workspace."""

    type: Literal["intent.predicted"] = "intent.predicted"
    prediction: IntentPrediction


class ContextEnriched(BaseEvent):
    """Contexto completo listo para pintar el workspace (pre-pop o refinado)."""

    type: Literal["context.enriched"] = "context.enriched"
    context: CallContext


# ──────────────────────────────────────────────────────────────────────────────
# Copiloto generativo
# ──────────────────────────────────────────────────────────────────────────────


class Citation(BaseModel):
    """Respaldo documental de una afirmación.

    Sin cita, la tarjeta no se muestra. Es la regla que impide que el copiloto
    invente una tarifa.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    chunk_id: str
    document: str
    section: str | None = None
    snippet: str
    score: float | None = None


class SuggestionStarted(BaseEvent):
    type: Literal["suggestion.started"] = "suggestion.started"
    suggestion_id: str
    trigger_turn_id: str
    speculative: bool = Field(
        default=False,
        description="Disparada antes de la certeza de fin de turno, para ganar latencia.",
    )


class SuggestionToken(BaseEvent):
    """Fragmento de la respuesta en streaming.

    La primera palabra a los ~300 ms importa más que la última a los 2 s.
    """

    type: Literal["suggestion.token"] = "suggestion.token"
    suggestion_id: str
    text: str


class SuggestionCompleted(BaseEvent):
    """Sugerencia terminada y validada por los guardarraíles."""

    type: Literal["suggestion.completed"] = "suggestion.completed"
    suggestion_id: str
    text: str
    citations: tuple[Citation, ...] = ()
    emotion_adapted_to: EmotionLabel | None = None
    blocked: bool = Field(
        default=False,
        description=(
            "True si un guardarraíl la detuvo: sin cita, cifra no verificada o frase prohibida."
        ),
    )
    blocked_reason: str | None = None
    latency_ms: int | None = None


class SuggestionFeedback(BaseEvent):
    """Qué hizo el ejecutivo con la sugerencia.

    Es la señal de calidad más valiosa que produce el sistema: alimenta la
    evaluación y, más adelante, el aprendizaje.
    """

    type: Literal["suggestion.feedback"] = "suggestion.feedback"
    suggestion_id: str
    action: Literal["used", "edited", "dismissed"]
    final_text: str | None = None


# ──────────────────────────────────────────────────────────────────────────────
# Reclamos (Ley 31763) y cierre
# ──────────────────────────────────────────────────────────────────────────────


class CaseClassified(BaseEvent):
    """Clasificación propuesta de reclamo vs. requerimiento.

    Clasificar mal un reclamo como requerimiento es un incumplimiento frente a
    la SBS. El copiloto propone CON justificación, el ejecutivo confirma, y la
    decisión queda auditada. La IA aquí reduce riesgo regulatorio en lugar de
    crearlo.
    """

    type: Literal["case.classified"] = "case.classified"
    proposed_type: CaseType | None = Field(
        default=None,
        description=(
            "None cuando la llamada se resolvió sin abrir caso. No es un hueco: es el "
            "desenlace de la mayoría de las disputas por cargo no reconocido, donde el "
            "cliente reconoce el consumo tras la explicación. Abrir un caso por cada una "
            "satura la operación y dispara plazos de la Ley 31763 sin motivo."
        ),
    )
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(description="Por qué, en lenguaje que el ejecutivo pueda contrastar.")
    evidence_turn_ids: tuple[str, ...] = ()
    citations: tuple[Citation, ...] = ()
    confirmed_by_agent: bool | None = Field(
        default=None, description="None mientras el ejecutivo no confirme ni corrija."
    )
    draft_case: Case | None = None


class SummaryReady(BaseEvent):
    """Cierre post-llamada: el 54% de las llamadas lo exige, ~3 min cada una."""

    type: Literal["summary.ready"] = "summary.ready"
    summary: str
    disposition: str
    commitments: tuple[str, ...] = Field(
        default=(), description="Compromisos adquiridos con el cliente, extraídos del diálogo."
    )
    citations: tuple[Citation, ...] = ()
    generated_at: datetime


# ──────────────────────────────────────────────────────────────────────────────
# Unión discriminada
# ──────────────────────────────────────────────────────────────────────────────

Event = Annotated[
    CallStarted
    | CallEnded
    | AsrPartial
    | AsrFinal
    | TurnEnded
    | EmotionFrame
    | EscalationAlert
    | NluTurn
    | RiskSignal
    | IntentPredicted
    | ContextEnriched
    | SuggestionStarted
    | SuggestionToken
    | SuggestionCompleted
    | SuggestionFeedback
    | CaseClassified
    | SummaryReady,
    Field(discriminator="type"),
]
