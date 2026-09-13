"""Acceso a Postgres.

Un pool asíncrono compartido por toda la aplicación. Las consultas se escriben
en SQL explícito y no con un ORM: el equipo de datos de un banco tiene que
poder leer exactamente qué se consulta, y las consultas del pre-pop tienen
presupuesto de latencia que hay que poder razonar.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

_pool: AsyncConnectionPool | None = None


async def open_pool(dsn: str) -> AsyncConnectionPool:
    global _pool
    _pool = AsyncConnectionPool(
        dsn, min_size=2, max_size=10, open=False, kwargs={"row_factory": dict_row}
    )
    await _pool.open(wait=True, timeout=10)
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def pool() -> AsyncConnectionPool:
    if _pool is None:
        raise RuntimeError("El pool no está abierto: falta el lifespan de la aplicación.")
    return _pool


@asynccontextmanager
async def cursor() -> AsyncIterator:
    async with pool().connection() as conn, conn.cursor() as cur:
        yield cur
