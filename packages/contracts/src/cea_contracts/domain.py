"""Modelos de dominio del copiloto.

Estos modelos describen lo que el ejecutivo ve en el workspace. El orden en que
aparecen refleja el orden de prioridad del diseño, que es el de la evidencia y
no el de la estructura de los sistemas de origen:

    identidad y confianza → por qué llama → evidencia para resolver → 360 completo
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from .enums import (
    AuthLevel,
    CallIntent,
    CaseStatus,
    CaseType,
    Channel,
    TransactionStatus,
    VulnerabilityKind,
)


class _Base(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


# ──────────────────────────────────────────────────────────────────────────────
# Zona 0 — Identidad y confianza
# ──────────────────────────────────────────────────────────────────────────────


class AuthFactor(_Base):
    """Un factor de verificación usado en la llamada."""

    kind: str = Field(description="ani_match | pregunta_seguridad | otp | voz | app_push")
    passed: bool
    detail: str | None = None


class TrustState(_Base):
    """Estado de verificación y riesgo. Va arriba de todo en el workspace.

    Ninguna otra información es utilizable si no se sabe con quién se habla, y
    ninguna acción sensible debe ofrecerse por encima del nivel alcanzado.
    """

    level: AuthLevel = AuthLevel.NO_VERIFICADO
    factors: tuple[AuthFactor, ...] = ()
    fraud_risk_score: float = Field(default=0.0, ge=0.0, le=1.0)
    synthetic_voice_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Probabilidad de habla sintética. Es UNA señal de riesgo entre varias, "
            "nunca una contraseña. En el MVP es simulada."
        ),
    )
    step_up_required_for: tuple[str, ...] = Field(
        default=(),
        description="Acciones que exigen elevar el nivel de verificación antes de ejecutarse.",
    )


# ──────────────────────────────────────────────────────────────────────────────
# Zona 2 — Evidencia para resolver: transacciones enriquecidas
# ──────────────────────────────────────────────────────────────────────────────


class Merchant(_Base):
    """Entrada del catálogo de comercios usado para resolver descriptores crudos."""

    merchant_id: str
    display_name: str
    legal_name: str | None = None
    category: str
    logo_url: str | None = None
    district: str | None = None
    city: str | None = None
    country: str = "PE"
    descriptor_patterns: tuple[str, ...] = Field(
        default=(),
        description="Patrones de descriptor crudo que resuelven a este comercio.",
    )


class Transaction(_Base):
    """Transacción tal como la ve el ejecutivo, ya enriquecida.

    El campo `raw_descriptor` se conserva a propósito: el cliente lo tiene a la
    vista en su estado de cuenta y el ejecutivo necesita poder tender el puente
    entre ese texto ilegible y el comercio real.
    """

    transaction_id: str
    account_id: str
    occurred_at: datetime
    amount: Decimal
    currency: str = "PEN"
    status: TransactionStatus
    channel: Channel

    raw_descriptor: str = Field(description="Lo que el cliente ve en su estado de cuenta.")

    # Enriquecimiento (services/enrichment)
    merchant: Merchant | None = None
    device_label: str | None = Field(
        default=None, description='Dispositivo desde el que se hizo, p. ej. "iPhone de Juan".'
    )
    decline_reason: str | None = Field(
        default=None, description="Motivo del rechazo en lenguaje humano, no el código crudo."
    )
    prior_purchases_90d: int = Field(
        default=0,
        ge=0,
        description=(
            "Compras previas en el mismo comercio en 90 días. Es el dato que más "
            "rápido cierra una disputa por cargo no reconocido."
        ),
    )
    is_recurring: bool = False


# ──────────────────────────────────────────────────────────────────────────────
# Zona 1 — Por qué llama
# ──────────────────────────────────────────────────────────────────────────────


class DigitalJourneyEvent(_Base):
    """Algo que el cliente intentó en la app, la web o el IVR antes de llamar.

    El canal telefónico se usa sobre todo cuando el autoservicio ya falló, así
    que esto es el arreglo más directo al "no me hagan repetir todo".
    """

    occurred_at: datetime
    channel: Channel
    screen: str = Field(description='Pantalla u opción, p. ej. "detalle_movimiento" o "IVR:2".')
    action: str
    succeeded: bool
    detail: str | None = None


class AccountEvent(_Base):
    """Evento de la cuenta con capacidad conocida de disparar una llamada."""

    occurred_at: datetime
    kind: str = Field(
        description=(
            "cargo_rechazado | tarjeta_bloqueada | transferencia_fallida | "
            "cuota_vencida | cobro_inusual"
        )
    )
    summary: str
    related_transaction_id: str | None = None
    severity: str = "info"


class Case(_Base):
    """Reclamo o requerimiento con su reloj regulatorio.

    Bajo la Ley 31763 la entidad tiene 15 días hábiles para responder un
    reclamo. El ejecutivo necesita ver si está hablando con alguien cuyo plazo
    vence mañana.
    """

    case_id: str
    folio: str
    customer_id: str
    case_type: CaseType
    status: CaseStatus
    opened_at: datetime
    due_at: datetime = Field(description="Vencimiento del plazo regulatorio (15 días hábiles).")
    subject: str
    summary: str | None = None
    related_transaction_id: str | None = None

    @property
    def is_overdue(self) -> bool:
        return datetime.now(self.due_at.tzinfo) > self.due_at


class IntentPrediction(_Base):
    """Motivo probable de la llamada, con su evidencia legible.

    Sin la evidencia el ejecutivo no confía en la predicción y deja de mirarla.
    """

    intent: CallIntent
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: tuple[str, ...] = Field(
        default=(), description="Razones en lenguaje natural, mostradas tal cual en la UI."
    )
    source: str = Field(
        default="pre_pop", description="pre_pop (antes de descolgar) | transcript (refinado)"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Zona 6 — 360 completo (colapsado por defecto en la UI)
# ──────────────────────────────────────────────────────────────────────────────


class ProductHolding(_Base):
    """Producto contratado por el cliente."""

    holding_id: str
    product_code: str
    product_name: str
    opened_at: date
    balance: Decimal | None = None
    credit_limit: Decimal | None = None
    currency: str = "PEN"
    status: str = "activo"
    masked_number: str | None = Field(
        default=None, description="Siempre enmascarado. El PAN completo nunca entra al sistema."
    )


class Customer(_Base):
    """Perfil del cliente.

    Deliberadamente NO es el elemento principal del workspace: vive en la Zona 6,
    colapsada. Lo que el ejecutivo necesita primero es el contexto de ESTA
    llamada, no la ficha completa.
    """

    customer_id: str
    full_name: str
    document_type: str = "DNI"
    document_masked: str = Field(
        description="Enmascarado: ***4521. El número completo no se guarda."
    )
    segment: str
    customer_since: date
    birth_date: date | None = None
    city: str | None = None
    district: str | None = None
    phone_masked: str | None = None
    email_masked: str | None = None
    nps: int | None = Field(default=None, ge=0, le=10)
    preferred_language: str = "es-PE"
    vulnerabilities: tuple[VulnerabilityKind, ...] = Field(
        default=(),
        description="Sólo vulnerabilidad DECLARADA. Inferirla queda en el backlog.",
    )
    holdings: tuple[ProductHolding, ...] = ()


# ──────────────────────────────────────────────────────────────────────────────
# El paquete completo que la API entrega al workspace
# ──────────────────────────────────────────────────────────────────────────────


class CallContext(_Base):
    """Todo lo que el workspace necesita para pintarse, en un solo objeto.

    Se calcula ANTES de descolgar (pre-pop) y se refina con los primeros turnos
    de la transcripción. Un solo viaje: el "toggle tax" empieza por no obligar
    al frontend a orquestar cinco llamadas.
    """

    call_id: str
    customer: Customer
    trust: TrustState
    intent: IntentPrediction
    recent_account_events: tuple[AccountEvent, ...] = ()
    digital_journey: tuple[DigitalJourneyEvent, ...] = ()
    open_cases: tuple[Case, ...] = ()
    relevant_transactions: tuple[Transaction, ...] = Field(
        default=(),
        description="Transacciones seleccionadas por la intención predicha, ya enriquecidas.",
    )
    focus_transaction_id: str | None = Field(
        default=None,
        description=(
            "La transacción que se está discutiendo. Sin esto el workspace no sabe "
            "qué resaltar y el ejecutivo tiene que buscarla a ojo en la lista, que es "
            "exactamente el trabajo manual que el producto existe para eliminar."
        ),
    )
    supporting_transaction_ids: tuple[str, ...] = Field(
        default=(),
        description=(
            "Compras ANTERIORES y liquidadas en el mismo comercio. Son la prueba que "
            "convierte 'no reconozco este cargo' en 'ya compró ahí seis veces'; sin "
            "ellas el copiloto no puede afirmar nada y la disputa escala igual."
        ),
    )
    related_attempt_ids: tuple[str, ...] = Field(
        default=(),
        description=(
            "Intentos posteriores en el mismo comercio, típicamente rechazados. "
            "Significan lo OPUESTO al historial de compras: un cliente que compra no "
            "reintenta el mismo monto tras un rechazo, un defraudador probando una "
            "tarjeta sí. Mezclarlos con las compras previas haría que el panel "
            "presente la evidencia del fraude como prueba de que el cliente es "
            "cliente habitual del comercio."
        ),
    )
    generated_at: datetime
