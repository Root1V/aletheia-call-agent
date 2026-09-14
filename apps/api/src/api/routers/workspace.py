"""Datos de apoyo del portal: resumen, clientes y conjunto de evaluación."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Query
from pydantic import BaseModel

from ..auth import CurrentAgent
from ..db import cursor

router = APIRouter(prefix="/api", tags=["portal"])


class Overview(BaseModel):
    llamadas_en_bandeja: int
    datos_sembrados_hace_horas: float | None = None
    """Antigüedad del dataset de demostración.

    Los escenarios colocan sus eventos en relación al momento de la siembra, y
    el contexto sólo mira las últimas 72 horas. Pasado ese plazo el panel
    aparece vacío SIN ningún error, que es la peor forma de fallar: parece que
    el producto no funciona. Exponerlo permite avisar a tiempo.
    """
    clientes: int
    transacciones: int
    comercios: int
    casos_abiertos: int
    casos_por_vencer: int
    documentos_kb: int
    llamadas_atendidas: int


@router.get("/stats/overview", response_model=Overview)
async def overview(agent: CurrentAgent) -> Overview:
    """Cifras del panel de inicio.

    Una sola consulta con subconsultas en vez de ocho viajes: son números
    pequeños e independientes, y encadenarlos multiplicaría la latencia por
    ocho sin ganar nada.
    """
    async with cursor() as cur:
        await cur.execute(
            """
            SELECT
              (SELECT count(*) FROM demo_scenarios)                        AS llamadas_en_bandeja,
              (SELECT count(*) FROM customers)                             AS clientes,
              (SELECT count(*) FROM transactions)                          AS transacciones,
              (SELECT count(*) FROM merchants)                             AS comercios,
              (SELECT count(*) FROM cases
                WHERE status NOT IN ('resuelto','cerrado'))                AS casos_abiertos,
              (SELECT count(*) FROM cases
                WHERE status NOT IN ('resuelto','cerrado')
                  AND due_at < now() + INTERVAL '7 days')                  AS casos_por_vencer,
              (SELECT count(*) FROM kb_documents)                          AS documentos_kb,
              (SELECT count(*) FROM calls)                                 AS llamadas_atendidas,
              (SELECT round(EXTRACT(EPOCH FROM (now() - seeded_at)) / 3600.0, 1)
                 FROM seed_info)                        AS datos_sembrados_hace_horas
            """
        )
        row = await cur.fetchone()
    return Overview(**row)


class CustomerRow(BaseModel):
    customer_id: str
    full_name: str
    document_masked: str
    segment: str
    city: str | None
    district: str | None
    customer_since: date
    productos: int
    casos_abiertos: int
    vulnerabilities: list[str]


@router.get("/customers", response_model=list[CustomerRow])
async def customers(
    agent: CurrentAgent,
    q: str = Query("", max_length=120),
    limit: int = Query(50, ge=1, le=200),
) -> list[CustomerRow]:
    """Listado de clientes con búsqueda por nombre o documento.

    La búsqueda usa `unaccent` para que "Sanchez" encuentre a "Sánchez": nadie
    escribe tildes en un buscador mientras tiene a alguien esperando al
    teléfono.
    """
    async with cursor() as cur:
        await cur.execute(
            """
            SELECT c.customer_id, c.full_name, c.document_masked, c.segment,
                   c.city, c.district, c.customer_since, c.vulnerabilities,
                   (SELECT count(*) FROM product_holdings p
                     WHERE p.customer_id = c.customer_id) AS productos,
                   (SELECT count(*) FROM cases k
                     WHERE k.customer_id = c.customer_id
                       AND k.status NOT IN ('resuelto','cerrado')) AS casos_abiertos
            FROM customers c
            WHERE %(q)s = ''
               OR unaccent(lower(c.full_name)) LIKE unaccent(lower('%%' || %(q)s || '%%'))
               OR c.document_masked LIKE '%%' || %(q)s || '%%'
            ORDER BY c.full_name
            LIMIT %(limit)s
            """,
            {"q": q.strip(), "limit": limit},
        )
        filas = await cur.fetchall()

    return [CustomerRow(**f) for f in filas]


class ScenarioRow(BaseModel):
    scenario_id: str
    customer_id: str
    customer_name: str
    expected_intent: str
    narrative: str
    expects_case: bool
    expected_case_type: str | None
    focus_amount: Decimal | None
    focus_descriptor: str | None
    focus_merchant: str | None
    prior_purchases_90d: int | None
    ordinal: int


@router.get("/evaluation/scenarios", response_model=list[ScenarioRow])
async def evaluation_scenarios(agent: CurrentAgent) -> list[ScenarioRow]:
    """Conjunto de evaluación con su verdad de referencia.

    Es lo que hace auditable al sistema: la misma tabla que alimenta la bandeja
    declara qué debería concluir el copiloto en cada caso, incluido el que NO
    debe terminar en reclamo. Poder mirar esa verdad de referencia en el portal
    evita la discusión de "¿contra qué se midió?" en la reunión de resultados.
    """
    async with cursor() as cur:
        await cur.execute(
            """
            SELECT s.scenario_id, s.customer_id, c.full_name AS customer_name,
                   s.expected_intent, s.narrative, s.expects_case,
                   s.expected_case_type, s.ordinal,
                   t.amount AS focus_amount, t.raw_descriptor AS focus_descriptor,
                   m.display_name AS focus_merchant, t.prior_purchases_90d
            FROM demo_scenarios s
            JOIN customers c USING (customer_id)
            LEFT JOIN transactions t ON t.transaction_id = s.focus_transaction_id
            LEFT JOIN merchants m ON m.merchant_id = t.merchant_id
            ORDER BY s.ordinal
            """
        )
        filas = await cur.fetchall()

    return [ScenarioRow(**f) for f in filas]


class RecentCall(BaseModel):
    call_id: str
    customer_name: str
    scenario_id: str | None
    agent_id: str
    started_at: datetime
    ended_at: datetime | None


@router.get("/calls/recent", response_model=list[RecentCall])
async def recent_calls(agent: CurrentAgent, limit: int = Query(8, ge=1, le=50)) -> list[RecentCall]:
    async with cursor() as cur:
        await cur.execute(
            """
            SELECT l.call_id, c.full_name AS customer_name, l.scenario_id,
                   l.agent_id, l.started_at, l.ended_at
            FROM calls l JOIN customers c USING (customer_id)
            ORDER BY l.started_at DESC LIMIT %s
            """,
            (limit,),
        )
        return [RecentCall(**f) for f in await cur.fetchall()]
