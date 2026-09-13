"""Escenarios de llamada coherentes.

Cada constructor devuelve un `Scenario` en el que todas las piezas encajan: el
cargo discutido, el historial que permite (o no) explicarlo, el evento de
cuenta, los intentos fallidos en la app, la opción marcada en el IVR y los
casos abiertos.

La distinción entre el primer escenario y el segundo es la que justifica todo
el flujo de reclamos del MVP:

- ``disputa_cargo_no_reconocido``: el cliente SÍ hizo la compra, pero el
  descriptor es ilegible. Hay compras previas en ese comercio. Se resuelve
  explicando, sin abrir caso. Es el 61% de las disputas.
- ``disputa_fraude``: el cliente NO hizo la compra. No hay historial con ese
  comercio, viene del exterior y hubo intentos adicionales. Debe abrirse un
  RECLAMO con su plazo regulatorio.

Confundir uno con otro en ambos sentidos es caro: explicar un fraude como si
fuera olvido deja al cliente desprotegido; abrir un reclamo por cada cargo mal
entendido satura la operación y dispara los plazos de la Ley 31763.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from cea_contracts import (
    AccountEvent,
    CallIntent,
    Case,
    CaseStatus,
    CaseType,
    Channel,
    DigitalJourneyEvent,
    Transaction,
    TransactionStatus,
)

from . import refdata as rd
from .generator import PeruBankGenerator, Scenario, _habiles_despues
from .timezone import fmt_fecha


def _journey_disputa(
    ahora: datetime, *, intentos: int = 3, con_ivr: bool = True
) -> tuple[DigitalJourneyEvent, ...]:
    """El recorrido típico antes de llamar: intentar en la app y no poder.

    El canal telefónico se usa sobre todo cuando el autoservicio ya falló. Que
    el ejecutivo vea ese rastro es el arreglo más directo al "no me hagan
    repetir todo".
    """
    eventos: list[DigitalJourneyEvent] = []
    base = ahora - timedelta(hours=2)

    eventos.append(
        DigitalJourneyEvent(
            occurred_at=base,
            channel=Channel.APP,
            screen="detalle_movimiento",
            action="consultar_cargo",
            succeeded=True,
            detail="Abrió el detalle del consumo",
        )
    )
    for i in range(intentos):
        eventos.append(
            DigitalJourneyEvent(
                occurred_at=base + timedelta(minutes=4 * (i + 1)),
                channel=Channel.APP,
                screen="reportar_consumo",
                action="iniciar_reporte",
                succeeded=False,
                detail="El formulario no avanzó del paso 2",
            )
        )
    eventos.append(
        DigitalJourneyEvent(
            occurred_at=base + timedelta(minutes=25),
            channel=Channel.APP,
            screen="ayuda_disputas",
            action="leer_ayuda",
            succeeded=True,
        )
    )
    if con_ivr:
        eventos.append(
            DigitalJourneyEvent(
                occurred_at=ahora - timedelta(minutes=2),
                channel=Channel.IVR,
                screen="IVR:2",
                action="reportar_consumo_no_reconocido",
                succeeded=True,
                detail="Reportar un consumo no reconocido",
            )
        )
    return tuple(eventos)


def disputa_cargo_no_reconocido(gen: PeruBankGenerator, idx: int = 1) -> Scenario:
    """El caso insignia: el cliente sí compró, pero el descriptor es ilegible.

    La resolución está en el propio panel: comercio real, dispositivo, hora y
    —sobre todo— las compras previas en ese mismo comercio.
    """
    rng = gen.rng
    ahora = datetime.now(UTC)
    cliente = gen.customer(idx)
    cuenta = cliente.holdings[0].holding_id

    comercio = rng.choice(gen.opaque_merchants(0.85))
    previas = rng.randint(3, 8)

    foco = gen.transaction(
        cuenta,
        comercio,
        ahora - timedelta(days=2, hours=5),
        amount=Decimal("189.90"),
        device_label=f"{rng.choice(rd.DISPOSITIVOS)} de {cliente.full_name.split()[0]}",
        prior_90d=previas,
    )

    # El historial que sostiene la explicación: si no existiera, el copiloto no
    # podría afirmar nada y la disputa tendría que escalar.
    historial: list[Transaction] = [foco]
    for i in range(previas):
        historial.append(
            gen.transaction(
                cuenta,
                comercio,
                ahora - timedelta(days=8 + i * 11, hours=rng.randint(0, 20)),
                device_label=foco.device_label,
                prior_90d=max(previas - i - 1, 0),
            )
        )
    historial.extend(gen.history(cliente, days=45, per_day=0.8)[:20])
    historial.sort(key=lambda t: t.occurred_at, reverse=True)

    eventos = (
        AccountEvent(
            occurred_at=foco.occurred_at,
            kind="cobro_inusual",
            summary=f"Consumo de S/ {foco.amount} en {foco.raw_descriptor}",
            related_transaction_id=foco.transaction_id,
            severity="info",
        ),
    )

    return Scenario(
        scenario_id="disputa_cargo_no_reconocido",
        intent=CallIntent.DISPUTA_CARGO_NO_RECONOCIDO,
        customer=cliente,
        transactions=tuple(historial),
        account_events=eventos,
        journey=_journey_disputa(ahora),
        open_cases=(),
        focus_transaction_id=foco.transaction_id,
        narrative=(
            f"El cliente no reconoce S/ {foco.amount} de '{foco.raw_descriptor}'. "
            f"Es {comercio.display_name}, donde ya compró {previas} veces en 90 días "
            f"desde su propio {foco.device_label}. Se resuelve explicando: no hay fraude "
            f"y no corresponde abrir un reclamo."
        ),
    )


def disputa_fraude(gen: PeruBankGenerator, idx: int = 2) -> Scenario:
    """Fraude real: sin historial con el comercio, desde el exterior, con reintentos.

    Aquí sí corresponde abrir un RECLAMO con su plazo de 15 días hábiles.
    """
    rng = gen.rng
    ahora = datetime.now(UTC)
    cliente = gen.customer(idx)
    cuenta = cliente.holdings[0].holding_id

    comercio = rng.choice([m for m in gen.merchants if m.category == "E-commerce"])

    foco = gen.transaction(
        cuenta,
        comercio,
        ahora - timedelta(hours=9),
        amount=Decimal("1450.00"),
        device_label=None,  # dispositivo desconocido: señal fuerte
        prior_90d=0,
    )
    # Los reintentos rechazados son la evidencia que distingue fraude de olvido.
    reintentos = [
        gen.transaction(
            cuenta,
            comercio,
            ahora - timedelta(hours=9) + timedelta(minutes=3 * (i + 1)),
            amount=Decimal("1450.00"),
            status=TransactionStatus.RECHAZADA,
            prior_90d=0,
        )
        for i in range(2)
    ]

    historial = [foco, *reintentos, *gen.history(cliente, days=45, per_day=0.9)[:20]]
    historial.sort(key=lambda t: t.occurred_at, reverse=True)

    eventos = (
        AccountEvent(
            occurred_at=foco.occurred_at,
            kind="cobro_inusual",
            summary=f"Consumo internacional de S/ {foco.amount} sin dispositivo reconocido",
            related_transaction_id=foco.transaction_id,
            severity="alto",
        ),
        AccountEvent(
            occurred_at=reintentos[-1].occurred_at,
            kind="cargo_rechazado",
            summary="2 intentos adicionales rechazados en el mismo comercio",
            related_transaction_id=reintentos[-1].transaction_id,
            severity="alto",
        ),
    )

    return Scenario(
        scenario_id="disputa_fraude",
        intent=CallIntent.DISPUTA_FRAUDE,
        customer=cliente,
        transactions=tuple(historial),
        account_events=eventos,
        journey=_journey_disputa(ahora, intentos=2),
        open_cases=(),
        focus_transaction_id=foco.transaction_id,
        narrative=(
            f"Consumo de S/ {foco.amount} en {comercio.display_name} sin historial previo, "
            f"desde un dispositivo desconocido, con 2 reintentos rechazados. "
            f"Corresponde RECLAMO con plazo de 15 días hábiles."
        ),
    )


def disputa_cobro_duplicado(gen: PeruBankGenerator, idx: int = 3) -> Scenario:
    """Dos cargos idénticos con minutos de diferencia: el caso más fácil de probar."""
    rng = gen.rng
    ahora = datetime.now(UTC)
    cliente = gen.customer(idx)
    cuenta = cliente.holdings[0].holding_id

    comercio = rng.choice(
        [m for m in gen.merchants if m.category in ("Supermercado", "Restaurante")]
    )
    monto = Decimal("243.60")
    cuando = ahora - timedelta(days=1, hours=3)

    primero = gen.transaction(cuenta, comercio, cuando, amount=monto, prior_90d=4)
    duplicado = gen.transaction(
        cuenta, comercio, cuando + timedelta(minutes=6), amount=monto, prior_90d=4
    )

    historial = [primero, duplicado, *gen.history(cliente, days=45, per_day=0.8)[:18]]
    historial.sort(key=lambda t: t.occurred_at, reverse=True)

    eventos = (
        AccountEvent(
            occurred_at=duplicado.occurred_at,
            kind="cobro_inusual",
            summary=(
                f"Dos consumos de S/ {monto} en {comercio.display_name} con 6 minutos de diferencia"
            ),
            related_transaction_id=duplicado.transaction_id,
            severity="medio",
        ),
    )

    return Scenario(
        scenario_id="disputa_cobro_duplicado",
        intent=CallIntent.DISPUTA_COBRO_DUPLICADO,
        customer=cliente,
        transactions=tuple(historial),
        account_events=eventos,
        journey=_journey_disputa(ahora, intentos=1),
        open_cases=(),
        focus_transaction_id=duplicado.transaction_id,
        narrative=(
            f"Dos cargos de S/ {monto} en {comercio.display_name} separados por 6 minutos. "
            f"Duplicado evidente: corresponde reclamo y extorno."
        ),
    )


def tarjeta_rechazada(gen: PeruBankGenerator, idx: int = 4) -> Scenario:
    """El cliente llama porque su tarjeta fue rechazada y no sabe por qué.

    Lo que baja la llamada no es el código del autorizador, es la frase que
    explica qué pasó y qué hacer.
    """
    rng = gen.rng
    ahora = datetime.now(UTC)
    cliente = gen.customer(idx)
    cuenta = cliente.holdings[0].holding_id
    comercio = rng.choice(gen.merchants)

    rechazo = gen.transaction(
        cuenta,
        comercio,
        ahora - timedelta(hours=4),
        status=TransactionStatus.RECHAZADA,
        prior_90d=rng.randint(0, 3),
    )
    historial = [rechazo, *gen.history(cliente, days=45, per_day=0.9)[:18]]
    historial.sort(key=lambda t: t.occurred_at, reverse=True)

    eventos = (
        AccountEvent(
            occurred_at=rechazo.occurred_at,
            kind="cargo_rechazado",
            summary=f"Consumo rechazado en {comercio.display_name}: {rechazo.decline_reason}",
            related_transaction_id=rechazo.transaction_id,
            severity="medio",
        ),
    )
    journey = (
        DigitalJourneyEvent(
            occurred_at=ahora - timedelta(minutes=40),
            channel=Channel.APP,
            screen="mis_tarjetas",
            action="revisar_estado",
            succeeded=True,
        ),
        DigitalJourneyEvent(
            occurred_at=ahora - timedelta(minutes=36),
            channel=Channel.APP,
            screen="limites_compra",
            action="consultar_limite",
            succeeded=False,
            detail="No encontró el motivo del rechazo",
        ),
        DigitalJourneyEvent(
            occurred_at=ahora - timedelta(minutes=2),
            channel=Channel.IVR,
            screen="IVR:0",
            action="hablar_con_ejecutivo",
            succeeded=True,
        ),
    )

    return Scenario(
        scenario_id="tarjeta_rechazada",
        intent=CallIntent.TARJETA_RECHAZADA,
        customer=cliente,
        transactions=tuple(historial),
        account_events=eventos,
        journey=journey,
        open_cases=(),
        focus_transaction_id=rechazo.transaction_id,
        narrative=(
            f"Tarjeta rechazada en {comercio.display_name}. Motivo real: "
            f"{rechazo.decline_reason} El cliente no lo encontró en la app."
        ),
    )


def seguimiento_reclamo_por_vencer(gen: PeruBankGenerator, idx: int = 5) -> Scenario:
    """Reclamo abierto con el plazo regulatorio a punto de vencer.

    Es el escenario que justifica el reloj de SLA: el ejecutivo debe saber que
    está hablando con alguien cuyo plazo vence en dos días, antes de abrir la
    boca.
    """
    rng = gen.rng
    ahora = datetime.now(UTC)
    cliente = gen.customer(idx)
    cuenta = cliente.holdings[0].holding_id
    comercio = rng.choice(gen.opaque_merchants(0.7))

    disputada = gen.transaction(
        cuenta, comercio, ahora - timedelta(days=13), amount=Decimal("520.00"), prior_90d=0
    )
    abierto = ahora - timedelta(days=13)
    caso = Case(
        case_id="CAS000913",
        folio=f"REC-2026-{rng.randint(10000, 99999)}",
        customer_id=cliente.customer_id,
        case_type=CaseType.RECLAMO,
        status=CaseStatus.EN_ANALISIS,
        opened_at=abierto,
        due_at=_habiles_despues(abierto, 15),
        subject=f"Consumo no reconocido de S/ {disputada.amount}",
        summary="El cliente desconoce el consumo y solicita extorno.",
        related_transaction_id=disputada.transaction_id,
    )

    historial = [disputada, *gen.history(cliente, days=45, per_day=0.8)[:15]]
    historial.sort(key=lambda t: t.occurred_at, reverse=True)

    eventos = (
        AccountEvent(
            occurred_at=abierto,
            kind="cobro_inusual",
            summary=f"Reclamo {caso.folio} en análisis",
            related_transaction_id=disputada.transaction_id,
            severity="medio",
        ),
    )
    journey = (
        DigitalJourneyEvent(
            occurred_at=ahora - timedelta(days=3),
            channel=Channel.APP,
            screen="estado_cuenta",
            action="consultar_reclamo",
            succeeded=False,
            detail="El estado del reclamo no se mostraba actualizado",
        ),
        DigitalJourneyEvent(
            occurred_at=ahora - timedelta(minutes=1),
            channel=Channel.IVR,
            screen="IVR:0",
            action="hablar_con_ejecutivo",
            succeeded=True,
        ),
    )

    return Scenario(
        scenario_id="seguimiento_reclamo_por_vencer",
        intent=CallIntent.SEGUIMIENTO_RECLAMO,
        customer=cliente,
        transactions=tuple(historial),
        account_events=eventos,
        journey=journey,
        open_cases=(caso,),
        focus_transaction_id=disputada.transaction_id,
        narrative=(
            f"Reclamo {caso.folio} abierto hace 13 días, vence "
            f"{fmt_fecha(caso.due_at)}. El cliente llama porque la app no le "
            f"mostraba el estado. Alta probabilidad de escalamiento."
        ),
    )


CONSTRUCTORES = {
    "disputa_cargo_no_reconocido": disputa_cargo_no_reconocido,
    "disputa_fraude": disputa_fraude,
    "disputa_cobro_duplicado": disputa_cobro_duplicado,
    "tarjeta_rechazada": tarjeta_rechazada,
    "seguimiento_reclamo_por_vencer": seguimiento_reclamo_por_vencer,
}


def build_all(seed: int = 2026) -> list[Scenario]:
    """Construye los cinco escenarios base del flujo de reclamos."""
    gen = PeruBankGenerator(seed=seed)
    return [fn(gen, idx) for idx, fn in enumerate(CONSTRUCTORES.values(), start=1)]
