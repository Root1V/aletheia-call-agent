"""Evaluación del pre-pop sobre el golden set.

Mide lo que el plan define como medible: si el motivo predicho antes de
descolgar coincide con el real, y si el contexto señala la transacción
correcta.
"""

from __future__ import annotations

import os
import time

import psycopg
import pytest
from api.services import context_builder
from cea_contracts import CallIntent, TransactionStatus


def _hay_datos() -> bool:
    try:
        with psycopg.connect(DSN, connect_timeout=2) as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM demo_scenarios")
            return (cur.fetchone() or (0,))[0] > 0
    except Exception:
        return False


DSN = os.environ.get("CEA_DATABASE_URL", "postgresql://cea:cea_dev@localhost:5432/cea")
pytestmark = pytest.mark.skipif(
    not _hay_datos(), reason="Sin base sembrada. Levantar infra y correr `make seed`."
)

# El pre-pop corre antes de descolgar y no compite con el presupuesto de la
# transcripción (700 ms), pero un margen amplio es lo que permite añadir
# después el enriquecimiento y el RAG sin rehacer la arquitectura.
PRESUPUESTO_PREPOP_MS = 150


async def test_predice_el_motivo_de_las_cinco_llamadas(escenarios) -> None:
    """Acierto de intención sobre el golden set completo."""
    fallos = []
    for sc in escenarios:
        ctx = await context_builder.build(f"call-{sc['scenario_id']}", sc["customer_id"])
        esperado = CallIntent(sc["expected_intent"])
        if ctx.intent.intent is not esperado:
            fallos.append(f"{sc['scenario_id']}: esperaba {esperado}, obtuvo {ctx.intent.intent}")

    assert not fallos, "Motivos mal predichos:\n" + "\n".join(fallos)


async def test_toda_prediccion_trae_evidencia_legible(escenarios) -> None:
    """Sin evidencia el ejecutivo deja de mirar el panel en una semana."""
    for sc in escenarios:
        ctx = await context_builder.build(f"call-{sc['scenario_id']}", sc["customer_id"])
        assert ctx.intent.evidence, f"{sc['scenario_id']} sin evidencia"
        assert ctx.intent.confidence <= 0.92, "el pre-pop no puede declararse infalible"


async def test_el_foco_apunta_al_cargo_donde_salio_el_dinero(escenarios) -> None:
    """En un fraude, el evento más reciente suele ser un reintento RECHAZADO.

    Señalarlo como foco lleva al ejecutivo a discutir una transacción por la
    que nunca salió dinero mientras el cargo real sigue en la cuenta.
    """
    sc = next(s for s in escenarios if s["scenario_id"] == "disputa_fraude")
    ctx = await context_builder.build("call-disputa_fraude", sc["customer_id"])

    foco = next(
        t for t in ctx.relevant_transactions if t.transaction_id == ctx.focus_transaction_id
    )
    assert foco.status is TransactionStatus.LIQUIDADA
    assert foco.prior_purchases_90d == 0
    assert foco.device_label is None


async def test_el_cargo_mal_entendido_trae_su_prueba(escenarios) -> None:
    """Las compras previas en el mismo comercio son lo que permite explicar.

    Sin ellas el copiloto no puede afirmar nada y la disputa escala igual, que
    es justo el desenlace que el producto existe para evitar.
    """
    sc = next(s for s in escenarios if s["scenario_id"] == "disputa_cargo_no_reconocido")
    ctx = await context_builder.build("call-disputa_cargo_no_reconocido", sc["customer_id"])

    assert len(ctx.supporting_transaction_ids) >= 3
    foco = next(
        t for t in ctx.relevant_transactions if t.transaction_id == ctx.focus_transaction_id
    )
    assert foco.merchant is not None
    apoyos = [
        t for t in ctx.relevant_transactions if t.transaction_id in ctx.supporting_transaction_ids
    ]
    assert all(t.merchant and t.merchant.merchant_id == foco.merchant.merchant_id for t in apoyos)


async def test_el_duplicado_gana_a_las_senales_circunstanciales(escenarios) -> None:
    """Evidencia exacta contra corazonadas.

    Dos cargos idénticos con minutos de diferencia no son indicio de
    duplicado: SON un duplicado. Si la suma de señales circunstanciales puede
    tumbar ese hecho, el motor está mal diseñado.
    """
    sc = next(s for s in escenarios if s["scenario_id"] == "disputa_cobro_duplicado")
    ctx = await context_builder.build("call-disputa_cobro_duplicado", sc["customer_id"])

    assert ctx.intent.intent is CallIntent.DISPUTA_COBRO_DUPLICADO
    assert any("minutos de diferencia" in e for e in ctx.intent.evidence)


async def test_el_reloj_regulatorio_llega_al_workspace(escenarios) -> None:
    """El ejecutivo debe saber que el plazo vence antes de abrir la boca."""
    sc = next(s for s in escenarios if s["scenario_id"] == "seguimiento_reclamo_por_vencer")
    ctx = await context_builder.build("call-seguimiento_reclamo_por_vencer", sc["customer_id"])

    assert ctx.open_cases, "el caso abierto no llegó al contexto"
    assert any("vence" in e for e in ctx.intent.evidence)


async def test_el_prepop_entra_en_presupuesto(escenarios) -> None:
    """El presupuesto de latencia es el requisito no funcional número uno."""
    peor = 0.0
    for sc in escenarios:
        inicio = time.perf_counter()
        await context_builder.build(f"call-{sc['scenario_id']}", sc["customer_id"])
        peor = max(peor, (time.perf_counter() - inicio) * 1000)

    assert peor < PRESUPUESTO_PREPOP_MS, f"pre-pop en {peor:.0f} ms"


async def test_ningun_documento_completo_sale_del_backend(escenarios) -> None:
    """El DNI y el PAN nunca deben viajar al frontend."""
    for sc in escenarios:
        ctx = await context_builder.build(f"call-{sc['scenario_id']}", sc["customer_id"])
        assert ctx.customer.document_masked.startswith("***")
        for h in ctx.customer.holdings:
            assert h.masked_number is None or h.masked_number.startswith("****")


async def test_los_intentos_del_fraude_no_se_cuentan_como_compras_previas(escenarios) -> None:
    """Dos grupos con significado OPUESTO, y confundirlos invierte la conclusión.

    Los reintentos rechazados del defraudador son posteriores al cargo, no
    anteriores. Contarlos como historial hacía que el panel anunciara "2
    compras previas en AliExpress" justo encima del aviso de que no había
    ninguna.
    """
    sc = next(s for s in escenarios if s["scenario_id"] == "disputa_fraude")
    ctx = await context_builder.build("call-disputa_fraude", sc["customer_id"])

    assert ctx.supporting_transaction_ids == (), "un fraude no tiene historial con el comercio"
    assert len(ctx.related_attempt_ids) >= 2, "los reintentos son la evidencia del fraude"

    foco = next(
        t for t in ctx.relevant_transactions if t.transaction_id == ctx.focus_transaction_id
    )
    intentos = [t for t in ctx.relevant_transactions if t.transaction_id in ctx.related_attempt_ids]
    assert all(t.occurred_at >= foco.occurred_at for t in intentos)


async def test_las_compras_previas_son_anteriores_y_liquidadas(escenarios) -> None:
    sc = next(s for s in escenarios if s["scenario_id"] == "disputa_cargo_no_reconocido")
    ctx = await context_builder.build("call-disputa_cargo_no_reconocido", sc["customer_id"])

    foco = next(
        t for t in ctx.relevant_transactions if t.transaction_id == ctx.focus_transaction_id
    )
    apoyos = [
        t for t in ctx.relevant_transactions if t.transaction_id in ctx.supporting_transaction_ids
    ]
    assert apoyos
    assert all(t.occurred_at < foco.occurred_at for t in apoyos)
    assert all(t.status is TransactionStatus.LIQUIDADA for t in apoyos)
    assert ctx.related_attempt_ids == ()


async def test_el_riesgo_mostrado_coincide_con_lo_que_el_banco_detecto(escenarios) -> None:
    """Un indicador que contradice al resto del panel enseña a no mirarlo."""
    fraude = next(s for s in escenarios if s["scenario_id"] == "disputa_fraude")
    normal = next(s for s in escenarios if s["scenario_id"] == "disputa_cargo_no_reconocido")

    alto = await context_builder.build("call-disputa_fraude", fraude["customer_id"])
    bajo = await context_builder.build("call-x", normal["customer_id"])

    assert alto.trust.fraud_risk_score >= 0.5
    assert bajo.trust.fraud_risk_score < 0.5
