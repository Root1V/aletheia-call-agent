"""Fixtures de los tests de RAG."""

from __future__ import annotations

import os

import pytest_asyncio
from api.db import close_pool, cursor, open_pool

DSN = os.environ.get("CEA_DATABASE_URL", "postgresql://cea:cea_dev@localhost:5432/cea")


@pytest_asyncio.fixture
async def db_cursor():
    await open_pool(DSN)
    try:
        async with cursor() as cur:
            yield cur
    finally:
        await close_pool()
