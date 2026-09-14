#!/usr/bin/env python
"""Indexa la base de conocimiento del banco.

uv run python scripts/index_kb.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, "services/rag/src")

from cea_rag import indexar  # noqa: E402

KB = Path("packages/synthetic-data/src/cea_synthetic/kb")
DSN = os.environ.get("CEA_DATABASE_URL", "postgresql://cea:cea_dev@localhost:5432/cea")


async def main() -> int:
    if not KB.exists():
        print(f"No existe {KB}", file=sys.stderr)
        return 1
    print(f"Indexando {KB} …")
    informe = await indexar(KB, DSN)
    print(f"Listo: {informe}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
