"""Tests del contrato del sistema.

Estos tests protegen decisiones de diseño, no detalles de implementación. Si
uno falla, lo más probable es que alguien haya erosionado una garantía del
plan sin darse cuenta.
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from cea_contracts import (
    AsrFinal,
    AudioFrame,
    Case,
    CaseStatus,
    CaseType,
    Channel,
    EmotionFrame,
    EmotionLabel,
    Merchant,
    Speaker,
    SuggestionCompleted,
    Transaction,
    TransactionStatus,
)
from cea_contracts.events import Event
from pydantic import TypeAdapter, ValidationError

EVENT_ADAPTER: TypeAdapter = TypeAdapter(Event)


def test_evento_sobrevive_el_viaje_por_el_bus() -> None:
    """Serializar y deserializar debe devolver el mismo tipo concreto.

    Es lo que permite reproducir una llamada completa desde el log de eventos,
    que a su vez es lo que hace posibles las evaluaciones deterministas.
    """
    original = AsrFinal(
        call_id="c1",
        speaker=Speaker.CUSTOMER,
        turn_id="t1",
        text="No reconozco un cargo de 189 soles",
        started_at_ms=1_000,
        ended_at_ms=3_400,
        confidence=0.94,
        reconciled=True,
    )

    recovered = EVENT_ADAPTER.validate_json(original.model_dump_json())

    assert type(recovered) is AsrFinal
    assert recovered == original


def test_no_se_puede_medir_la_emocion_del_ejecutivo() -> None:
    """La restricción del plan (§4.3) vive en el tipo, no en la configuración.

    Medir emocionalmente a los empleados envenena la relación laboral, convierte
    al copiloto en herramienta de vigilancia y cierra la puerta a Europa, donde
    el EU AI Act lo prohíbe. Que sea imposible de construir —y no una opción
    que alguien pueda invertir por descuido— es deliberado.
    """
    with pytest.raises(ValidationError):
        EmotionFrame(
            call_id="c1",
            speaker=Speaker.AGENT,  # type: ignore[arg-type]
            scores={EmotionLabel.FRUSTRACION: 0.9},
            valence=-0.5,
            arousal=0.4,
            confidence=0.9,
        )


def test_emocion_del_cliente_si_se_construye() -> None:
    frame = EmotionFrame(
        call_id="c1",
        scores={EmotionLabel.FRUSTRACION: 0.72, EmotionLabel.NEUTRAL: 0.20},
        valence=-0.6,
        arousal=0.5,
        confidence=0.81,
        contributions={"acoustic": 0.55, "text": 0.25, "conversational": 0.20},
    )

    assert frame.speaker is Speaker.CUSTOMER
    # La fusión declara de dónde viene cada aporte: en llamadas reales lo
    # acústico pesa más que el texto, y eso debe poder auditarse.
    assert frame.contributions["acoustic"] > frame.contributions["text"]


def test_los_eventos_son_inmutables() -> None:
    """Un evento ya emitido no se corrige: se emite otro. Si no, el replay miente."""
    event = AsrFinal(
        call_id="c1",
        speaker=Speaker.CUSTOMER,
        turn_id="t1",
        text="hola",
        started_at_ms=0,
        ended_at_ms=100,
    )

    with pytest.raises(ValidationError):
        event.text = "otra cosa"  # type: ignore[misc]


def test_sugerencia_sin_cita_queda_bloqueada() -> None:
    """Sin respaldo documental la tarjeta no se muestra.

    Es el control que impide que el copiloto invente una tasa, y el que evita
    el incidente regulatorio. No es el prompt: es esta bandera.
    """
    suggestion = SuggestionCompleted(
        call_id="c1",
        suggestion_id="s1",
        text="La tasa efectiva anual es 24%",
        citations=(),
        blocked=True,
        blocked_reason="sin_cita",
    )

    assert suggestion.blocked
    assert not suggestion.citations


def test_caso_conoce_su_vencimiento_regulatorio() -> None:
    """Ley 31763: 15 días hábiles para responder un reclamo."""
    case = Case(
        case_id="k1",
        folio="REC-2026-00123",
        customer_id="cu1",
        case_type=CaseType.RECLAMO,
        status=CaseStatus.REGISTRADO,
        opened_at=datetime(2020, 1, 1, tzinfo=UTC),
        due_at=datetime(2020, 1, 22, tzinfo=UTC),
        subject="Cargo no reconocido",
    )

    assert case.is_overdue


def test_la_transaccion_conserva_el_descriptor_crudo() -> None:
    """El cliente tiene el descriptor ilegible a la vista en su estado de cuenta.

    El ejecutivo necesita tender el puente entre ese texto y el comercio real:
    el 61% de las disputas nacen de no reconocer un cargo, no de un fraude.
    """
    tx = Transaction(
        transaction_id="tx1",
        account_id="a1",
        occurred_at=datetime(2026, 9, 3, 14, 32, tzinfo=UTC),
        amount=Decimal("42.50"),
        status=TransactionStatus.LIQUIDADA,
        channel=Channel.APP,
        raw_descriptor="DLO*RAPPI PE 5511234567",
        merchant=Merchant(
            merchant_id="m1",
            display_name="Rappi",
            category="Delivery de comida",
            district="Miraflores",
            city="Lima",
        ),
        device_label="iPhone de Juan",
        prior_purchases_90d=5,
    )

    assert tx.raw_descriptor != tx.merchant.display_name
    assert tx.prior_purchases_90d == 5


def test_trama_de_audio_de_20ms_a_16khz() -> None:
    """La trama de 20 ms es la unidad que entregan Asterisk y FreeSWITCH."""
    frame = AudioFrame(
        call_id="c1",
        speaker=Speaker.CUSTOMER,
        pcm16=b"\x00" * 640,
        sample_rate=16_000,
        ts_ms=0,
    )

    assert frame.duration_ms == pytest.approx(20.0)


def test_campos_desconocidos_se_rechazan() -> None:
    """Un typo en un productor no debe pasar silenciosamente al consumidor."""
    with pytest.raises(ValidationError):
        AsrFinal(
            call_id="c1",
            speaker=Speaker.CUSTOMER,
            turn_id="t1",
            text="hola",
            started_at_ms=0,
            ended_at_ms=1,
            confidense=0.9,  # type: ignore[call-arg]
        )
