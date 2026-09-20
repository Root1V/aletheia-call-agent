"""Generador de datos sintéticos de banca peruana.

La dificultad de este módulo no es producir volumen: es producir COHERENCIA.
Un escenario de disputa sólo sirve para demostrar el copiloto si el cargo
discutido, las compras previas en ese mismo comercio, el evento de cuenta, los
intentos fallidos en la app y la predicción de intención encajan entre sí. Si
no encajan, la demo se cae ante la primera pregunta del comité.

Todo es determinista a partir de una semilla: el golden set de evaluaciones
depende de poder regenerar exactamente los mismos datos.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from cea_contracts import (
    AccountEvent,
    AuthFactor,
    CallContext,
    CallIntent,
    Case,
    CaseType,
    Channel,
    Customer,
    DigitalJourneyEvent,
    IntentPrediction,
    Merchant,
    ProductHolding,
    Transaction,
    TransactionStatus,
    TrustState,
    VulnerabilityKind,
)
from cea_contracts.enums import AuthLevel

from . import refdata as rd
from .timezone import fmt_fecha, fmt_fecha_hora

_DOMINIOS = ("gmail.com", "hotmail.com", "outlook.com")


def _weighted(rng: random.Random, pairs: tuple[tuple[str, float], ...]) -> str:
    return rng.choices([p[0] for p in pairs], weights=[p[1] for p in pairs], k=1)[0]


def _poisson(rng: random.Random, lam: float) -> int:
    """Muestra una Poisson por el método de Knuth.

    El gasto diario de una persona se parece mucho más a una Poisson que a un
    número fijo de compras: hay días sin consumo y días con cuatro. Con un
    conteo constante el historial se ve artificial de inmediato.
    """
    limite = math.exp(-lam)
    k, p = 0, 1.0
    while True:
        p *= rng.random()
        if p <= limite:
            return k
        k += 1


@dataclass(slots=True)
class Scenario:
    """Un caso de llamada completo y coherente, listo para demo o evaluación."""

    scenario_id: str
    intent: CallIntent
    customer: Customer
    transactions: tuple[Transaction, ...]
    account_events: tuple[AccountEvent, ...]
    journey: tuple[DigitalJourneyEvent, ...]
    open_cases: tuple[Case, ...]
    focus_transaction_id: str | None
    narrative: str = ""
    """Qué está pasando, en una línea, para el guion de la demo."""

    expects_case: bool = True
    """Si la atención correcta termina abriendo un caso.

    Es False en el cargo mal entendido: la resolución correcta es explicar, no
    abrir un reclamo. Distinguir ese caso de los demás es justamente lo que el
    evaluador tiene que medir, porque abrir un reclamo por cada cargo no
    reconocido satura la operación y dispara los plazos de la Ley 31763.
    """

    expected_case_type: CaseType | None = None
    """Clasificación correcta cuando sí corresponde abrir caso."""

    def to_call_context(self, call_id: str, now: datetime) -> CallContext:
        """Arma el pre-pop: todo lo que el workspace necesita para pintarse."""
        return CallContext(
            call_id=call_id,
            customer=self.customer,
            trust=_trust_for(self.customer, now),
            intent=_predict_intent(self),
            recent_account_events=self.account_events,
            digital_journey=self.journey,
            open_cases=self.open_cases,
            relevant_transactions=self.transactions,
            generated_at=now,
        )


def _trust_for(customer: Customer, now: datetime) -> TrustState:
    """Estado de verificación simulado.

    En el MVP es simulado a propósito: la biometría de voz real, con detección
    de habla sintética y de vivacidad, es un proyecto en sí mismo y está en el
    backlog. Lo que sí es real aquí es la FORMA: la voz nunca aparece como
    factor único ni como contraseña.
    """
    return TrustState(
        level=AuthLevel.VERIFICADO,
        factors=(
            AuthFactor(kind="ani_match", passed=True, detail="Llama desde el número registrado"),
            AuthFactor(kind="pregunta_seguridad", passed=True, detail="Último dígito del DNI"),
        ),
        fraud_risk_score=0.08,
        synthetic_voice_score=0.03,
        step_up_required_for=("transferencia", "aumento_linea", "cambio_datos_contacto"),
    )


def _predict_intent(scenario: Scenario) -> IntentPrediction:
    """Predicción de motivo con su evidencia legible.

    La evidencia no es decorativa: sin ella el ejecutivo no confía en la
    predicción y deja de mirar el panel a la semana.
    """
    evidencia: list[str] = []

    for ev in scenario.account_events[:2]:
        evidencia.append(f"{ev.summary} ({fmt_fecha_hora(ev.occurred_at)})")

    fallidos = [j for j in scenario.journey if not j.succeeded and j.channel is Channel.APP]
    if fallidos:
        evidencia.append(f"{len(fallidos)} intentos fallidos en la app ({fallidos[0].screen})")

    ivr = [j for j in scenario.journey if j.channel is Channel.IVR]
    if ivr:
        evidencia.append(f"Marcó {ivr[-1].screen} en el IVR")

    if scenario.open_cases:
        c = scenario.open_cases[0]
        evidencia.append(f"Caso abierto {c.folio}, vence {fmt_fecha(c.due_at)}")

    # La confianza sube con la cantidad de evidencia concordante, y se mantiene
    # por debajo de 1.0: una predicción que se declara segura y se equivoca
    # cuesta más credibilidad que una prudente.
    confianza = min(0.45 + 0.13 * len(evidencia), 0.92)

    return IntentPrediction(
        intent=scenario.intent,
        confidence=round(confianza, 2),
        evidence=tuple(evidencia),
        source="pre_pop",
    )


class PeruBankGenerator:
    """Genera clientes, comercios, transacciones y escenarios coherentes."""

    def __init__(self, seed: int = 2026) -> None:
        self.rng = random.Random(seed)
        self.merchants: tuple[Merchant, ...] = self._build_merchants()
        self._by_name = {m.display_name: m for m in self.merchants}

    # ── catálogo ──────────────────────────────────────────────────────────────

    def _build_merchants(self) -> tuple[Merchant, ...]:
        out: list[Merchant] = []
        for idx, (nombre, categoria, distrito, descriptores, _op) in enumerate(
            rd.CATALOGO_COMERCIOS
        ):
            out.append(
                Merchant(
                    merchant_id=f"MER{idx:04d}",
                    display_name=nombre,
                    category=categoria,
                    district=distrito,
                    city="Lima" if distrito else None,
                    descriptor_patterns=descriptores,
                    logo_url=f"/logos/{nombre.lower().replace(' ', '-').replace('+', 'plus')}.svg",
                )
            )
        return tuple(out)

    def _opacity(self, merchant: Merchant) -> float:
        for nombre, _c, _d, _desc, op in rd.CATALOGO_COMERCIOS:
            if nombre == merchant.display_name:
                return op
        return 0.5

    def opaque_merchants(self, min_opacity: float = 0.7) -> list[Merchant]:
        """Comercios cuyo descriptor crudo es ilegible: los que generan disputas."""
        return [m for m in self.merchants if self._opacity(m) >= min_opacity]

    # ── clientes ──────────────────────────────────────────────────────────────

    def customer(self, idx: int) -> Customer:
        rng = self.rng
        es_mujer = rng.random() < 0.5
        nombre = rng.choice(rd.NOMBRES_F if es_mujer else rd.NOMBRES_M)
        ap1, ap2 = rng.sample(rd.APELLIDOS, 2)
        full_name = f"{nombre} {ap1} {ap2}"

        dni = f"{rng.randint(10_000_000, 79_999_999)}"
        ciudad = _weighted(rng, rd.CIUDADES)
        distrito = rng.choice(rd.DISTRITOS_LIMA) if ciudad in ("Lima", "Callao") else None

        edad = rng.randint(21, 78)
        nacimiento = date(2026 - edad, rng.randint(1, 12), rng.randint(1, 28))
        antiguedad_anios = min(rng.randint(0, 22), edad - 18)

        # La vulnerabilidad es DECLARADA, nunca inferida (ver backlog del plan).
        vulnerabilidades: list[VulnerabilityKind] = []
        if edad >= 70 and rng.random() < 0.55:
            vulnerabilidades.append(VulnerabilityKind.ADULTO_MAYOR)
        if rng.random() < 0.04:
            vulnerabilidades.append(
                rng.choice(
                    [VulnerabilityKind.DISCAPACIDAD_AUDITIVA, VulnerabilityKind.DISCAPACIDAD_VISUAL]
                )
            )

        return Customer(
            customer_id=f"CUS{idx:06d}",
            full_name=full_name,
            document_type="DNI",
            document_masked=f"***{dni[-4:]}",
            segment=_weighted(rng, rd.SEGMENTOS),
            customer_since=date(2026 - antiguedad_anios, rng.randint(1, 12), rng.randint(1, 28)),
            birth_date=nacimiento,
            city=ciudad,
            district=distrito,
            phone_masked=f"9**{rng.randint(100000, 999999)}"[:6] + "***",
            email_masked=f"{nombre[:2].lower()}***@{rng.choice(_DOMINIOS)}",
            nps=rng.choice([None, *range(0, 11)]),
            vulnerabilities=tuple(vulnerabilidades),
            holdings=self._holdings(idx),
        )

    def _holdings(self, idx: int) -> tuple[ProductHolding, ...]:
        rng = self.rng
        out: list[ProductHolding] = []

        # Toda persona tiene al menos una cuenta.
        base = rng.choice([p for p in rd.PRODUCTOS if p[0].startswith("CTA_")])
        elegidos = [base]
        for producto in rd.PRODUCTOS:
            if producto in elegidos:
                continue
            if rng.random() < 0.22:
                elegidos.append(producto)

        for n, (code, name, kind) in enumerate(elegidos[:5]):
            saldo = credito = None
            if kind == "deposito":
                saldo = Decimal(rng.randrange(50, 4_500_00)) / 100
            elif kind == "credito":
                credito = Decimal(rng.choice([3_000, 5_000, 8_000, 12_000, 20_000, 35_000]))
                saldo = -(Decimal(rng.randrange(0, int(credito * 70))) / 100)

            out.append(
                ProductHolding(
                    holding_id=f"HLD{idx:06d}{n:02d}",
                    product_code=code,
                    product_name=name,
                    opened_at=date(rng.randint(2010, 2026), rng.randint(1, 12), rng.randint(1, 28)),
                    balance=saldo,
                    credit_limit=credito,
                    # Nunca el PAN completo: enmascarado desde el origen.
                    masked_number=f"****{rng.randint(1000, 9999)}" if kind != "deposito" else None,
                )
            )
        return tuple(out)

    # ── transacciones ────────────────────────────────────────────────────────

    def transaction(
        self,
        account_id: str,
        merchant: Merchant,
        occurred_at: datetime,
        *,
        amount: Decimal | None = None,
        status: TransactionStatus = TransactionStatus.LIQUIDADA,
        device_label: str | None = None,
        prior_90d: int = 0,
        recurring: bool = False,
        decline_reason: str | None = None,
    ) -> Transaction:
        rng = self.rng
        descriptor = rng.choice(merchant.descriptor_patterns or (merchant.display_name,))

        if amount is None:
            rangos = {
                "Delivery": (18, 95),
                "Transporte": (8, 60),
                "Supermercado": (35, 480),
                "Farmacia": (12, 220),
                "Restaurante": (25, 180),
                "Cafetería": (10, 45),
                "Combustible": (40, 250),
                "Suscripción digital": (16, 65),
                "E-commerce": (25, 900),
                "Telecomunicaciones": (20, 160),
            }
            lo, hi = rangos.get(merchant.category, (20, 400))
            amount = Decimal(rng.randrange(lo * 100, hi * 100)) / 100

        canal = Channel.ECOMMERCE if merchant.district is None else Channel.POS
        if merchant.category in ("Delivery", "Transporte", "Suscripción digital"):
            canal = Channel.APP

        motivo = decline_reason
        if motivo is None and status is TransactionStatus.RECHAZADA:
            motivo = rng.choice(rd.MOTIVOS_RECHAZO)[1]

        return Transaction(
            transaction_id=f"TRX{rng.randrange(10**11, 10**12)}",
            account_id=account_id,
            occurred_at=occurred_at,
            amount=amount,
            status=status,
            channel=canal,
            raw_descriptor=descriptor,
            merchant=merchant,
            device_label=device_label,
            decline_reason=motivo,
            prior_purchases_90d=prior_90d,
            is_recurring=recurring,
        )

    def history(
        self, customer: Customer, *, days: int = 90, per_day: float = 1.4
    ) -> list[Transaction]:
        """Historial de fondo. Da verosimilitud al panel y contexto al enriquecimiento."""
        rng = self.rng
        cuenta = customer.holdings[0].holding_id
        ahora = datetime.now(UTC)
        out: list[Transaction] = []

        habituales = rng.sample(self.merchants, k=min(8, len(self.merchants)))

        for d in range(days):
            for _ in range(_poisson(rng, per_day)):
                merchant = (
                    rng.choice(habituales) if rng.random() < 0.72 else rng.choice(self.merchants)
                )
                cuando = ahora - timedelta(
                    days=d, hours=rng.randint(0, 23), minutes=rng.randint(0, 59)
                )
                out.append(self.transaction(cuenta, merchant, cuando))

        return sorted(out, key=lambda t: t.occurred_at, reverse=True)
