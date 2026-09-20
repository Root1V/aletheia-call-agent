#!/usr/bin/env python
"""¿Aguanta el copiloto un piloto de nueve ejecutivos a la vez?

    uv run python evals/runners/carga_copiloto.py [--ejecutivos 9] [--minutos 2]

Simula N llamadas simultáneas publicando turnos en el bus al ritmo medido sobre
los guiones reales, y deja que el orquestador de verdad los atienda contra la
plataforma de verdad. No reemplaza el audio: salta el reconocimiento a propósito
para aislar lo que se quiere medir —la capacidad del copiloto y el presupuesto
de peticiones— de la contención de CPU del ASR, que en una sola máquina
enmascara todo lo demás.

Lo que responde:

- si las nueve llamadas producen las sugerencias que deberían, o si alguna se
  queda sin copiloto sin que nadie se entere
- si el presupuesto de peticiones aguanta (tres bolsas de 60/min desde el 19/09)
- cuánto se degrada la latencia con carga, que es distinto de medirla con una
  llamada sola
"""

from __future__ import annotations

import argparse
import asyncio
import os
import statistics
import sys
import time
import uuid

from cea_bus import EventBus
from cea_contracts import AsrFinal, CallEnded, CallStarted, ContextEnriched, Speaker, TurnEnded

sys.path.insert(0, "apps/api/src")

REDIS = os.environ.get("CEA_REDIS_URL", "redis://localhost:6380/0")
DSN = os.environ.get("CEA_DATABASE_URL", "postgresql://cea:cea_dev@localhost:5432/cea")

# Ritmo medido sobre los dos guiones reales: 5 turnos elegibles en ~86-94 s.
SEGUNDOS_ENTRE_TURNOS = 17.0

TURNOS = [
    "No reconozco este cargo de ciento ochenta y nueve soles en mi tarjeta",
    "Díganme cuánto cuesta la membresía anual de la tarjeta oro",
    "¿Cuánto se demoran en responderme esto que estoy reclamando?",
    "Se me perdió la tarjeta, ¿cuánto me cobran por mandarme otra?",
    "¿Por qué me rechazaron la compra si yo tengo saldo suficiente?",
]


async def _una_llamada(
    bus: EventBus, call_id: str, contexto, minutos: float, desfase: float
) -> None:
    """Publica los turnos de un ejecutivo al ritmo real.

    El `desfase` importa más de lo que parece. Arrancar las nueve llamadas a la
    vez las deja sincronizadas para siempre —todas terminan turno en el mismo
    instante— y produce ráfagas de nueve generaciones simultáneas que ningún
    centro de llamadas real genera. Medir así no mide el piloto: mide un
    escenario imposible, y el número que sale de ahí no se puede presentar.
    """
    await asyncio.sleep(desfase)
    await bus.reset(call_id)
    await bus.guardar_contexto(ContextEnriched(call_id=call_id, context=contexto))
    await bus.publish(
        CallStarted(
            call_id=call_id,
            customer_id="CUS000001",
            agent_id=call_id,
            room=call_id,
            ingress="carga",
            sample_rate=16000,
        )
    )
    fin = time.perf_counter() + minutos * 60
    i = 0
    while time.perf_counter() < fin:
        turn_id = f"t{i}"
        texto = TURNOS[i % len(TURNOS)]
        await bus.publish(
            AsrFinal(
                call_id=call_id,
                speaker=Speaker.CUSTOMER,
                turn_id=turn_id,
                text=texto,
                started_at_ms=i * 17000,
                ended_at_ms=i * 17000 + 4000,
            )
        )
        await bus.publish(TurnEnded(call_id=call_id, speaker=Speaker.CUSTOMER, turn_id=turn_id))
        i += 1
        await asyncio.sleep(SEGUNDOS_ENTRE_TURNOS)
    await bus.publish(CallEnded(call_id=call_id, duration_ms=int(minutos * 60_000)))


async def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Carga del copiloto con N ejecutivos simultáneos.")
    p.add_argument("--ejecutivos", type=int, default=9)
    p.add_argument("--minutos", type=float, default=2.0)
    p.add_argument(
        "--sincronizadas",
        action="store_true",
        help="Todas las llamadas a la vez. Es el peor caso y no es realista; por defecto se "
        "reparten a lo largo del intervalo entre turnos, como ocurre de verdad.",
    )
    args = p.parse_args(argv)

    from api.db import close_pool, open_pool
    from api.services import context_builder

    await open_pool(DSN)
    contexto = await context_builder.build("plantilla", "CUS000001")
    await close_pool()

    marca = uuid.uuid4().hex[:6]
    ids = [f"carga-{marca}-{n:02d}" for n in range(args.ejecutivos)]
    bus = EventBus.desde_url(REDIS, bloqueo_ms=5000)

    esperado = int(args.minutos * 60 / SEGUNDOS_ENTRE_TURNOS)
    print(
        f"\n  {args.ejecutivos} ejecutivos · {args.minutos:.0f} min · "
        f"~{esperado} turnos cada uno · {args.ejecutivos * esperado} sugerencias esperadas"
    )
    print(
        f"  ritmo: {args.ejecutivos * 60 / SEGUNDOS_ENTRE_TURNOS:.1f} sugerencias/min "
        f"= otras tantas peticiones/min en cada una de las tres bolsas (límite 60)\n"
    )
    print("  El orquestador tiene que estar corriendo: `make copilot`\n")

    paso = 0.0 if args.sincronizadas else SEGUNDOS_ENTRE_TURNOS / args.ejecutivos
    arranque = (
        "todas a la vez (peor caso)" if args.sincronizadas else f"escalonado cada {paso:.1f} s"
    )
    print(f"  arranque: {arranque}\n")

    inicio = time.perf_counter()
    await asyncio.gather(
        *(
            _una_llamada(bus, c, contexto.model_copy(update={"call_id": c}), args.minutos, n * paso)
            for n, c in enumerate(ids)
        )
    )
    # Margen para que termine lo que quedó en vuelo.
    await asyncio.sleep(20)

    mostrables = bloqueadas = 0
    latencias: list[float] = []
    motivos: dict[str, int] = {}
    sin_cerrar = 0
    por_llamada: dict[str, int] = {}

    for c in ids:
        abiertas = set()
        for _i, ev in await bus.history(c):
            if ev.type == "suggestion.started":
                abiertas.add(ev.suggestion_id)
            elif ev.type == "suggestion.completed":
                abiertas.discard(ev.suggestion_id)
                por_llamada[c] = por_llamada.get(c, 0) + 1
                if ev.blocked:
                    bloqueadas += 1
                    motivos[ev.blocked_reason or "?"] = motivos.get(ev.blocked_reason or "?", 0) + 1
                else:
                    mostrables += 1
                if ev.latency_ms:
                    latencias.append(float(ev.latency_ms))
        sin_cerrar += len(abiertas)

    total = mostrables + bloqueadas
    print(f"  ── {time.perf_counter() - inicio:.0f} s ──")
    print(
        f"  sugerencias: {total} de {args.ejecutivos * esperado} esperadas "
        f"({mostrables} mostrables, {bloqueadas} bloqueadas)"
    )
    print(f"  llamadas atendidas: {len(por_llamada)} de {args.ejecutivos}")
    if sin_cerrar:
        print(f"  ⚠ {sin_cerrar} tarjetas se quedaron sin cerrar (el portal seguiría 'redactando')")
    if latencias:
        latencias.sort()
        p50 = statistics.median(latencias)
        p90 = latencias[int(len(latencias) * 0.9)] if len(latencias) > 1 else latencias[0]
        print(
            f"  latencia: p50 {p50:.0f} ms · p90 {p90:.0f} ms · máx {max(latencias):.0f} ms"
            f"  (presupuesto 1500)"
        )
        print(f"  dentro de presupuesto: {sum(x <= 1500 for x in latencias)}/{len(latencias)}")
    for motivo, n in sorted(motivos.items(), key=lambda kv: -kv[1]):
        print(f"     {n:3}× {motivo[:78]}")

    vacias = [c for c in ids if c not in por_llamada]
    if vacias:
        print(f"  ⚠ sin copiloto: {', '.join(vacias)}")

    await bus.aclose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
