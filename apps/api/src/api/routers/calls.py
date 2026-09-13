"""Llamadas: bandeja de entrantes y contexto de la llamada."""

from __future__ import annotations

import time
import uuid

from cea_contracts import CallContext
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from ..auth import CurrentAgent
from ..config import get_settings
from ..db import cursor
from ..services import context_builder

router = APIRouter(prefix="/api/calls", tags=["llamadas"])


class InboundCall(BaseModel):
    """Una llamada entrante en la bandeja del ejecutivo.

    En el MVP proviene de un escenario guionado. Cuando entre la telefonía real
    llegará del ACD, pero la forma que consume el frontend no cambia.
    """

    call_id: str
    customer_id: str
    customer_name: str
    segment: str
    scenario_id: str
    narrative: str


class ContextResponse(BaseModel):
    context: CallContext
    build_ms: float
    """Cuánto tardó armar el contexto previo a descolgar."""

    budget_ms: int
    """Umbral contra el que juzgar `build_ms`.

    Viaja en la misma respuesta que la medición para que el portal no tenga que
    consultarlo aparte ni, peor, llevar su propia copia del número: dos sitios
    con el mismo umbral acaban discrepando.
    """


@router.get("/inbound", response_model=list[InboundCall])
async def inbound(agent: CurrentAgent) -> list[InboundCall]:
    """Bandeja de llamadas entrantes simuladas."""
    async with cursor() as cur:
        await cur.execute(
            """
            SELECT s.scenario_id, s.customer_id, s.narrative, c.full_name, c.segment
            FROM demo_scenarios s
            JOIN customers c USING (customer_id)
            ORDER BY s.ordinal
            """
        )
        filas = await cur.fetchall()

    return [
        InboundCall(
            # Determinista por escenario: recargar el portal no inventa llamadas
            # nuevas ni pierde la que estaba en curso.
            call_id=f"call-{f['scenario_id']}",
            customer_id=f["customer_id"],
            customer_name=f["full_name"],
            segment=f["segment"],
            scenario_id=f["scenario_id"],
            narrative=f["narrative"],
        )
        for f in filas
    ]


@router.get("/{call_id}/context", response_model=ContextResponse)
async def call_context(call_id: str, agent: CurrentAgent) -> ContextResponse:
    """Pre-pop: todo lo que el workspace necesita, en un solo viaje.

    Devolverlo junto no es una comodidad del backend: obligar al frontend a
    orquestar cinco llamadas reintroduce el mismo "toggle tax" que el producto
    intenta eliminar, sólo que dentro de la propia aplicación.
    """
    async with cursor() as cur:
        await cur.execute(
            "SELECT customer_id FROM demo_scenarios WHERE scenario_id = %s",
            (call_id.removeprefix("call-"),),
        )
        fila = await cur.fetchone()

    if fila is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Llamada desconocida: {call_id}")

    inicio = time.perf_counter()
    contexto = await context_builder.build(call_id, fila["customer_id"])
    transcurrido = (time.perf_counter() - inicio) * 1000

    return ContextResponse(
        context=contexto,
        build_ms=round(transcurrido, 1),
        budget_ms=get_settings().budget_context_ms,
    )


class AnswerRequest(BaseModel):
    room: str | None = None


@router.post("/{call_id}/answer", status_code=status.HTTP_201_CREATED)
async def answer(call_id: str, body: AnswerRequest, agent: CurrentAgent) -> dict:
    """Registra que el ejecutivo tomó la llamada.

    Crea la fila de `calls`, que es la raíz del log de eventos: sin ella no hay
    dónde anclar el replay ni la auditoría.
    """
    scenario_id = call_id.removeprefix("call-")
    async with cursor() as cur:
        await cur.execute(
            "SELECT customer_id FROM demo_scenarios WHERE scenario_id = %s", (scenario_id,)
        )
        fila = await cur.fetchone()
        if fila is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Llamada desconocida: {call_id}")

        room = body.room or f"cea-{scenario_id}-{uuid.uuid4().hex[:8]}"
        await cur.execute(
            """
            INSERT INTO calls (call_id, customer_id, agent_id, room, ingress, scenario_id)
            VALUES (%s, %s, %s, %s, 'livekit', %s)
            ON CONFLICT (call_id) DO UPDATE
                SET agent_id = EXCLUDED.agent_id, room = EXCLUDED.room, ended_at = NULL
            RETURNING room
            """,
            (call_id, fila["customer_id"], agent.agent_id, room, scenario_id),
        )
        creada = await cur.fetchone()

    return {"call_id": call_id, "room": creada["room"], "agent_id": agent.agent_id}
