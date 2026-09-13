"""Fixtures de los tests de la API.

Son tests de integración contra Postgres real, no contra mocks. Un mock del
motor de base de datos no habría detectado ninguno de los defectos que
aparecieron al construir el pre-pop: ni el orden de los eventos que hacía
señalar el reintento rechazado en vez del cargo cobrado, ni la resolución
difusa de descriptores. Si la base no está levantada, se omiten.
"""

from __future__ import annotations

import os

import psycopg
import pytest
import pytest_asyncio
from api.db import close_pool, open_pool

DSN = os.environ.get("CEA_DATABASE_URL", "postgresql://cea:cea_dev@localhost:5432/cea")


def _hay_datos() -> bool:
    try:
        with psycopg.connect(DSN, connect_timeout=2) as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM demo_scenarios")
            return (cur.fetchone() or (0,))[0] > 0
    except Exception:
        return False


requiere_datos = pytest.mark.skipif(
    not _hay_datos(),
    reason="Sin base sembrada. Levantar infra y correr `make seed`.",
)


@pytest_asyncio.fixture
async def db():
    await open_pool(DSN)
    try:
        yield
    finally:
        await close_pool()


@pytest_asyncio.fixture
async def escenarios(db) -> list[dict]:
    from api.db import cursor

    async with cursor() as cur:
        await cur.execute(
            """
            SELECT scenario_id, customer_id, expected_intent, focus_transaction_id,
                   expects_case, expected_case_type
            FROM demo_scenarios ORDER BY ordinal
            """
        )
        return list(await cur.fetchall())
