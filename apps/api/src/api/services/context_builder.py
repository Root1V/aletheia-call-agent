"""Construcción del contexto de llamada (pre-pop).

Está en el camino crítico: se ejecuta antes de que el ejecutivo descuelgue y
alimenta las zonas 0, 1, 2 y 6 del workspace de una sola vez.

Dos decisiones de diseño que no son obvias:

1. **Un solo viaje.** El contexto completo se devuelve en un objeto. Obligar al
   frontend a orquestar cinco llamadas reintroduce por la puerta de atrás el
   mismo "toggle tax" que el producto intenta eliminar.

2. **Transacciones seleccionadas por la intención.** No se devuelve el extracto
   entero: se devuelven las transacciones que hacen falta para resolver ESTE
   motivo. Un panel con 300 movimientos no es contexto, es ruido.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from cea_contracts import (
    AccountEvent,
    AuthFactor,
    CallContext,
    CallIntent,
    Case,
    CaseStatus,
    CaseType,
    Channel,
    Customer,
    DigitalJourneyEvent,
    Merchant,
    ProductHolding,
    Transaction,
    TransactionStatus,
    TrustState,
    VulnerabilityKind,
)
from cea_contracts.enums import AuthLevel

from ..db import cursor
from .intent_rules import Señales, predecir

# Ventana de "reciente". 72 horas cubre el fin de semana: un cargo del viernes
# por la noche genera la llamada del lunes por la mañana, y con 24 h ese caso
# —muy frecuente— se quedaría sin contexto.
VENTANA_RECIENTE = timedelta(hours=72)

# Motivos para los que el panel de evidencia debe mostrar transacciones.
_MOTIVOS_CON_TRANSACCIONES = {
    CallIntent.DISPUTA_CARGO_NO_RECONOCIDO,
    CallIntent.DISPUTA_FRAUDE,
    CallIntent.DISPUTA_COBRO_DUPLICADO,
    CallIntent.DISPUTA_SERVICIO_NO_RECIBIDO,
    CallIntent.TARJETA_RECHAZADA,
    CallIntent.CONSULTA_MOVIMIENTO,
    CallIntent.SEGUIMIENTO_RECLAMO,
}


async def build(call_id: str, customer_id: str) -> CallContext:
    """Arma el contexto completo de una llamada entrante."""
    ahora = datetime.now(UTC)
    desde = ahora - VENTANA_RECIENTE

    async with cursor() as cur:
        customer = await _customer(cur, customer_id)
        eventos = await _account_events(cur, customer_id, desde)
        journey = await _journey(cur, customer_id, desde)
        casos = await _open_cases(cur, customer_id)
        duplicados = await _duplicates(cur, customer_id, desde)

        prediccion = predecir(
            Señales(
                account_events=eventos,
                journey=journey,
                open_cases=casos,
                focus_transaction=None,
                duplicates=duplicados,
            )
        )

        transacciones: tuple[Transaction, ...] = ()
        foco_id: str | None = None
        soporte: tuple[str, ...] = ()
        intentos: tuple[str, ...] = ()
        if prediccion.intent in _MOTIVOS_CON_TRANSACCIONES:
            transacciones, foco_id, soporte, intentos = await _relevant_transactions(
                cur, customer_id, eventos, casos
            )

    return CallContext(
        call_id=call_id,
        customer=customer,
        trust=_trust(customer, eventos),
        intent=prediccion,
        recent_account_events=tuple(_to_account_event(e) for e in eventos),
        digital_journey=tuple(_to_journey_event(j) for j in journey),
        open_cases=tuple(_to_case(k) for k in casos),
        relevant_transactions=transacciones,
        focus_transaction_id=foco_id,
        supporting_transaction_ids=soporte,
        related_attempt_ids=intentos,
        generated_at=ahora,
    )


# ── consultas ────────────────────────────────────────────────────────────────


async def _customer(cur, customer_id: str) -> Customer:
    await cur.execute(
        """
        SELECT customer_id, full_name, document_type, document_masked, segment,
               customer_since, birth_date, city, district, phone_masked,
               email_masked, nps, preferred_language, vulnerabilities
        FROM customers WHERE customer_id = %s
        """,
        (customer_id,),
    )
    row = await cur.fetchone()
    if row is None:
        raise LookupError(f"Cliente no encontrado: {customer_id}")

    await cur.execute(
        """
        SELECT holding_id, product_code, product_name, opened_at, balance,
               credit_limit, currency, status, masked_number
        FROM product_holdings WHERE customer_id = %s ORDER BY opened_at
        """,
        (customer_id,),
    )
    holdings = tuple(
        ProductHolding(
            holding_id=h["holding_id"],
            product_code=h["product_code"],
            product_name=h["product_name"],
            opened_at=h["opened_at"],
            balance=h["balance"],
            credit_limit=h["credit_limit"],
            currency=h["currency"],
            status=h["status"],
            masked_number=h["masked_number"],
        )
        for h in await cur.fetchall()
    )

    return Customer(
        customer_id=row["customer_id"],
        full_name=row["full_name"],
        document_type=row["document_type"],
        document_masked=row["document_masked"],
        segment=row["segment"],
        customer_since=row["customer_since"],
        birth_date=row["birth_date"],
        city=row["city"],
        district=row["district"],
        phone_masked=row["phone_masked"],
        email_masked=row["email_masked"],
        nps=row["nps"],
        preferred_language=row["preferred_language"],
        vulnerabilities=tuple(VulnerabilityKind(v) for v in (row["vulnerabilities"] or ())),
        holdings=holdings,
    )


async def _account_events(cur, customer_id: str, desde: datetime) -> list[dict]:
    await cur.execute(
        """
        SELECT occurred_at, kind, summary, related_transaction_id, severity
        FROM account_events
        WHERE customer_id = %s AND occurred_at >= %s
        ORDER BY occurred_at DESC LIMIT 6
        """,
        (customer_id, desde),
    )
    return list(await cur.fetchall())


async def _journey(cur, customer_id: str, desde: datetime) -> list[dict]:
    await cur.execute(
        """
        SELECT occurred_at, channel, screen, action, succeeded, detail
        FROM digital_journey_events
        WHERE customer_id = %s AND occurred_at >= %s
        ORDER BY occurred_at
        LIMIT 15
        """,
        (customer_id, desde),
    )
    return list(await cur.fetchall())


async def _duplicates(cur, customer_id: str, desde: datetime) -> list[dict]:
    """Cargos duplicados: mismo comercio, mismo monto, minutos de diferencia.

    Detección exacta y barata. La ventana de 30 minutos separa el duplicado
    técnico —un reintento del terminal que se cobró dos veces— de dos compras
    legítimas en el mismo sitio el mismo día, que es algo que pasa a diario en
    una cafetería o un grifo.
    """
    await cur.execute(
        """
        SELECT a.transaction_id AS primero,
               b.transaction_id AS segundo,
               a.amount,
               COALESCE(m.display_name, a.raw_descriptor) AS merchant,
               EXTRACT(EPOCH FROM (b.occurred_at - a.occurred_at)) / 60 AS minutos
        FROM transactions a
        JOIN transactions b
          ON b.customer_id = a.customer_id
         AND b.merchant_id IS NOT DISTINCT FROM a.merchant_id
         AND b.amount = a.amount
         AND b.occurred_at > a.occurred_at
         AND b.occurred_at <= a.occurred_at + INTERVAL '30 minutes'
         AND b.transaction_id <> a.transaction_id
        LEFT JOIN merchants m ON m.merchant_id = a.merchant_id
        WHERE a.customer_id = %s
          AND a.occurred_at >= %s
          AND a.status = 'liquidada'
          AND b.status = 'liquidada'
        ORDER BY a.occurred_at DESC
        LIMIT 3
        """,
        (customer_id, desde),
    )
    return [
        {
            "primero": r["primero"],
            "segundo": r["segundo"],
            "amount": r["amount"],
            "merchant": r["merchant"],
            "minutos": int(r["minutos"]),
        }
        for r in await cur.fetchall()
    ]


async def _open_cases(cur, customer_id: str) -> list[dict]:
    await cur.execute(
        """
        SELECT case_id, folio, case_type, status, opened_at, due_at, subject,
               summary, related_transaction_id
        FROM cases
        WHERE customer_id = %s AND status NOT IN ('resuelto','cerrado')
        ORDER BY due_at
        """,
        (customer_id,),
    )
    return list(await cur.fetchall())


def _elegir_foco(filas: list[dict], candidatos: list[str]) -> str | None:
    """Cuál de las transacciones señaladas es la que se está discutiendo.

    No sirve tomar la primera: los eventos llegan del más reciente al más
    antiguo, y en un fraude el evento más reciente suele ser un REINTENTO
    RECHAZADO, no el cargo que efectivamente se cobró. Señalar el rechazo como
    foco lleva al ejecutivo a discutir una transacción por la que nunca salió
    dinero, mientras el cargo real sigue en la cuenta.

    Criterio: primero las que se liquidaron —ahí está el dinero del cliente— y
    entre ellas la de mayor monto.
    """
    if not candidatos:
        return None
    señaladas = [r for r in filas if r["transaction_id"] in set(candidatos)]
    if not señaladas:
        return None
    return min(
        señaladas,
        key=lambda r: (0 if r["status"] == "liquidada" else 1, -float(r["amount"])),
    )["transaction_id"]


async def _relevant_transactions(
    cur, customer_id: str, eventos: list[dict], casos: list[dict]
) -> tuple[tuple[Transaction, ...], str | None, tuple[str, ...], tuple[str, ...]]:
    """Transacciones que hacen falta para resolver el motivo detectado.

    Trae la transacción señalada por el evento o el caso, y a su alrededor el
    historial del MISMO comercio. Ese historial es lo que convierte "no
    reconozco este cargo" en "ya compró ahí seis veces": sin él, el copiloto no
    puede afirmar nada y la disputa escala igual.
    """
    focos = [e["related_transaction_id"] for e in eventos if e["related_transaction_id"]]
    focos += [k["related_transaction_id"] for k in casos if k["related_transaction_id"]]

    await cur.execute(
        """
        WITH foco AS (
            SELECT t.transaction_id, t.merchant_id
            FROM transactions t
            WHERE t.transaction_id = ANY(%s)
        ),
        relevantes AS (
            -- Las transacciones señaladas por los eventos y casos.
            SELECT t.* FROM transactions t JOIN foco f USING (transaction_id)
            UNION
            -- El historial con el mismo comercio, que es la prueba.
            SELECT t.* FROM transactions t
            WHERE t.customer_id = %s
              AND t.merchant_id IN (SELECT merchant_id FROM foco WHERE merchant_id IS NOT NULL)
            UNION
            -- Y los movimientos más recientes, para dar contexto general.
            SELECT t.* FROM (
                SELECT * FROM transactions
                WHERE customer_id = %s ORDER BY occurred_at DESC LIMIT 12
            ) t
        )
        SELECT r.transaction_id, r.account_id, r.occurred_at, r.amount, r.currency,
               r.status, r.channel, r.raw_descriptor, r.device_label,
               r.decline_reason, r.prior_purchases_90d, r.is_recurring,
               m.merchant_id, m.display_name, m.legal_name, m.category,
               m.logo_url, m.district, m.city, m.country
        FROM relevantes r
        LEFT JOIN merchants m ON m.merchant_id = r.merchant_id
        ORDER BY r.occurred_at DESC
        LIMIT 40
        """,
        (focos or [""], customer_id, customer_id),
    )

    filas = list(await cur.fetchall())
    foco_id = _elegir_foco(filas, focos)

    salida: list[Transaction] = []
    merchant_del_foco: str | None = None
    for r in filas:
        if r["transaction_id"] == foco_id:
            merchant_del_foco = r["merchant_id"]
    for r in filas:
        merchant = None
        if r["merchant_id"]:
            merchant = Merchant(
                merchant_id=r["merchant_id"],
                display_name=r["display_name"],
                legal_name=r["legal_name"],
                category=r["category"],
                logo_url=r["logo_url"],
                district=r["district"],
                city=r["city"],
                country=r["country"],
            )
        salida.append(
            Transaction(
                transaction_id=r["transaction_id"],
                account_id=r["account_id"],
                occurred_at=r["occurred_at"],
                amount=Decimal(r["amount"]),
                currency=r["currency"],
                status=TransactionStatus(r["status"]),
                channel=Channel(r["channel"]),
                raw_descriptor=r["raw_descriptor"],
                merchant=merchant,
                device_label=r["device_label"],
                decline_reason=r["decline_reason"],
                prior_purchases_90d=r["prior_purchases_90d"],
                is_recurring=r["is_recurring"],
            )
        )

    # Las transacciones del mismo comercio se parten en dos grupos que
    # significan cosas OPUESTAS, y confundirlos invierte la conclusión:
    #
    # - Compras ANTERIORES y liquidadas: prueba de que el cliente es cliente
    #   habitual del comercio. Sostienen la explicación.
    # - Intentos POSTERIORES, típicamente rechazados: prueba de lo contrario.
    #   Un cliente que compra no reintenta el mismo monto tras un rechazo; un
    #   defraudador probando una tarjeta, sí.
    #
    # Contarlos juntos hacía que el panel anunciara "2 compras previas en
    # AliExpress" justo encima del aviso de que no había ninguna.
    fila_foco = next((r for r in filas if r["transaction_id"] == foco_id), None)
    momento_foco = fila_foco["occurred_at"] if fila_foco else None

    soporte: list[str] = []
    intentos: list[str] = []
    if merchant_del_foco and momento_foco is not None:
        for r in filas:
            if r["merchant_id"] != merchant_del_foco or r["transaction_id"] == foco_id:
                continue
            if r["occurred_at"] < momento_foco and r["status"] == "liquidada":
                soporte.append(r["transaction_id"])
            elif r["occurred_at"] >= momento_foco:
                intentos.append(r["transaction_id"])

    return tuple(salida), foco_id, tuple(soporte), tuple(intentos)


# ── conversiones ─────────────────────────────────────────────────────────────


def _to_account_event(r: dict) -> AccountEvent:
    return AccountEvent(
        occurred_at=r["occurred_at"],
        kind=r["kind"],
        summary=r["summary"],
        related_transaction_id=r["related_transaction_id"],
        severity=r["severity"],
    )


def _to_journey_event(r: dict) -> DigitalJourneyEvent:
    return DigitalJourneyEvent(
        occurred_at=r["occurred_at"],
        channel=Channel(r["channel"]),
        screen=r["screen"],
        action=r["action"],
        succeeded=r["succeeded"],
        detail=r["detail"],
    )


def _to_case(r: dict) -> Case:
    return Case(
        case_id=r["case_id"],
        folio=r["folio"],
        customer_id="",  # ya se conoce por el contexto; no se repite en el payload
        case_type=CaseType(r["case_type"]),
        status=CaseStatus(r["status"]),
        opened_at=r["opened_at"],
        due_at=r["due_at"],
        subject=r["subject"],
        summary=r["summary"],
        related_transaction_id=r["related_transaction_id"],
    )


def _riesgo_fraude(eventos: list[dict]) -> float:
    """Riesgo derivado de la severidad que asignó el monitoreo del banco.

    SIMULADO en el MVP, como todo el estado de verificación. Lo que no es
    simulado es la coherencia: el indicador tiene que reflejar la misma
    evidencia que el resto del panel.
    """
    severidades = {e["severity"] for e in eventos}
    if "critico" in severidades:
        return 0.88
    if "alto" in severidades:
        return 0.71
    if "medio" in severidades:
        return 0.34
    return 0.08


def _trust(customer: Customer, eventos: list[dict]) -> TrustState:
    """Estado de verificación.

    SIMULADO en el MVP, y conviene decirlo sin ambigüedad. Lo que sí es real
    aquí es la forma: la voz nunca aparece como factor único ni como
    contraseña, sino como una señal de riesgo entre varias. La biometría
    pasiva con detección de habla sintética y vivacidad es un proyecto en sí
    mismo y está en el backlog.
    """
    return TrustState(
        level=AuthLevel.VERIFICADO,
        factors=(
            AuthFactor(kind="ani_match", passed=True, detail="Llama desde el número registrado"),
            AuthFactor(
                kind="pregunta_seguridad", passed=True, detail="Último dígito del documento"
            ),
        ),
        # El riesgo se deriva de lo que el monitoreo del propio banco ya marcó.
        # Una barra que anuncia "riesgo de fraude bajo" sobre un caso que el
        # banco clasificó como severidad alta no es sólo incoherente: le enseña
        # al ejecutivo a no mirar el indicador.
        fraud_risk_score=_riesgo_fraude(eventos),
        synthetic_voice_score=0.03,
        step_up_required_for=("transferencia", "aumento_linea", "cambio_datos_contacto"),
    )
