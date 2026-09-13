"""Tests del generador sintético.

Protegen la COHERENCIA de los escenarios, que es lo único que hace que la demo
resista preguntas, y la aritmética regulatoria, que tiene consecuencia legal.
"""

from datetime import UTC, datetime, timedelta

import pytest

from cea_contracts import CallIntent, CaseType, TransactionStatus
from cea_synthetic.generator import PeruBankGenerator, _habiles_despues
from cea_synthetic.scenarios import build_all
from cea_synthetic.timezone import LIMA, fmt_fecha_hora, to_lima


def test_los_dias_habiles_saltan_el_fin_de_semana() -> None:
    """El plazo de la Ley 31763 es en días HÁBILES, no corridos.

    Contarlo como corridos adelanta el vencimiento y hace que el panel dispare
    alarmas falsas de SLA.
    """
    # Viernes 4 de setiembre de 2026, 15:00 en Lima.
    viernes = datetime(2026, 9, 4, 15, 0, tzinfo=LIMA).astimezone(UTC)

    un_dia = _habiles_despues(viernes, 1)
    assert to_lima(un_dia).weekday() == 0, "1 día hábil desde viernes cae lunes"

    quince = _habiles_despues(viernes, 15)
    # 15 días hábiles cruzan tres fines de semana: son 21 días corridos.
    assert (to_lima(quince).date() - to_lima(viernes).date()).days == 21
    assert to_lima(quince).weekday() < 5


def test_las_horas_se_muestran_en_hora_de_lima() -> None:
    """Un consumo de las 20:25 en Lima no puede mostrarse como 01:25.

    Es el error que delata una demo bancaria peruana en el primer vistazo.
    """
    # 12/09/2026 20:25 en Lima == 13/09/2026 01:25 UTC.
    utc = datetime(2026, 9, 13, 1, 25, tzinfo=UTC)

    assert fmt_fecha_hora(utc) == "12/09 20:25"


@pytest.mark.parametrize("escenario", build_all(seed=2026), ids=lambda s: s.scenario_id)
def test_el_escenario_es_internamente_coherente(escenario) -> None:
    """La transacción en foco debe existir en el historial que se muestra."""
    ids = {t.transaction_id for t in escenario.transactions}
    assert escenario.focus_transaction_id in ids

    ctx = escenario.to_call_context("call-test", datetime.now(UTC))
    assert ctx.intent.intent is escenario.intent
    assert ctx.intent.evidence, "sin evidencia el ejecutivo deja de mirar la predicción"
    assert 0.0 < ctx.intent.confidence < 1.0, "una predicción nunca se declara infalible"


def test_cargo_no_reconocido_es_explicable_sin_abrir_caso() -> None:
    """El caso insignia: hay historial previo, así que se resuelve explicando.

    Sin compras previas en el mismo comercio el copiloto no podría afirmar
    nada, y la disputa tendría que escalar igual.
    """
    escenario = next(s for s in build_all() if s.scenario_id == "disputa_cargo_no_reconocido")
    foco = next(t for t in escenario.transactions if t.transaction_id == escenario.focus_transaction_id)

    assert foco.prior_purchases_90d >= 3, "sin historial no hay explicación posible"
    assert foco.device_label, "el dispositivo propio del cliente es parte de la prueba"
    assert foco.raw_descriptor != foco.merchant.display_name, "el descriptor debe ser opaco"
    assert not escenario.open_cases, "no corresponde abrir caso: el cliente sí compró"


def test_fraude_no_tiene_historial_ni_dispositivo_conocido() -> None:
    """El contraste con el caso anterior es lo que justifica el flujo completo."""
    escenario = next(s for s in build_all() if s.scenario_id == "disputa_fraude")
    foco = next(t for t in escenario.transactions if t.transaction_id == escenario.focus_transaction_id)

    assert foco.prior_purchases_90d == 0
    assert foco.device_label is None
    # Los reintentos rechazados son la evidencia que separa fraude de olvido.
    rechazos = [t for t in escenario.transactions if t.status is TransactionStatus.RECHAZADA]
    assert len(rechazos) >= 2


def test_reclamo_por_vencer_tiene_el_plazo_corriendo() -> None:
    escenario = next(s for s in build_all() if s.scenario_id == "seguimiento_reclamo_por_vencer")
    caso = escenario.open_cases[0]

    assert caso.case_type is CaseType.RECLAMO
    assert not caso.is_overdue, "el escenario es 'por vencer', no 'vencido'"
    restante = caso.due_at - datetime.now(UTC)
    assert timedelta(0) < restante < timedelta(days=10)


def test_la_semilla_hace_el_dataset_reproducible() -> None:
    """El golden set depende de poder regenerar exactamente los mismos datos."""
    a = build_all(seed=99)
    b = build_all(seed=99)

    assert [s.customer.full_name for s in a] == [s.customer.full_name for s in b]
    assert [s.focus_transaction_id for s in a] == [s.focus_transaction_id for s in b]


def test_los_documentos_siempre_llegan_enmascarados() -> None:
    """El DNI completo no debe existir en el modelo que viaja al frontend."""
    gen = PeruBankGenerator(seed=1)
    for i in range(25):
        cliente = gen.customer(i)
        assert cliente.document_masked.startswith("***")
        assert len(cliente.document_masked) == 7
        for h in cliente.holdings:
            if h.masked_number:
                assert h.masked_number.startswith("****")


def test_intencion_pertenece_a_la_taxonomia() -> None:
    """Una taxonomía corta y cerrada es lo que se etiqueta de forma fiable."""
    for escenario in build_all():
        assert isinstance(escenario.intent, CallIntent)
