"""Salud y presupuesto de latencia."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from ..config import Settings, get_settings
from ..db import cursor

router = APIRouter(tags=["salud"])


@router.get("/health")
async def health(settings: Annotated[Settings, Depends(get_settings)]) -> dict:
    """Estado del servicio y presupuesto de latencia vigente.

    El presupuesto se expone aquí para que el panel de Grafana, los tests de
    carga y las evaluaciones comparen contra el MISMO número y no contra
    constantes duplicadas en tres sitios.
    """
    try:
        async with cursor() as cur:
            await cur.execute("SELECT count(*) AS n FROM demo_scenarios")
            row = await cur.fetchone()
            db = {"ok": True, "escenarios": row["n"]}
    except Exception as exc:  # noqa: BLE001 - el health debe reportar, no romper
        db = {"ok": False, "error": str(exc)}

    return {
        "status": "ok" if db["ok"] else "degradado",
        "auth_mode": settings.auth_mode,
        "postgres": db,
        "presupuesto_latencia_ms": {
            "transcripcion_visible": settings.budget_transcript_ms,
            "sugerencia_visible": settings.budget_suggestion_ms,
        },
    }
