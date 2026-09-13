#!/usr/bin/env python
"""Reproduce un escenario guionado como si fuera una llamada en vivo.

    uv run cea-replay --scenario disputa_cargo_no_reconocido

El portal, abierto en la llamada correspondiente, muestra la transcripción
apareciendo en tiempo real. Es la demo de la Fase 1 y, con `--velocidad`, la
forma de correr el pipeline completo en los tests sin esperar setenta segundos.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

from cea_asr import SherpaStreamingASR
from cea_bus import EventBus

from .ingest.file_replay import FileReplayAdapter
from .pipeline import CallPipeline

MODELO = Path("models/sherpa-onnx-streaming-zipformer-es-kroko-2025-08-06")
RAIZ_AUDIO = Path("evals/audio")


async def reproducir(
    scenario_id: str,
    *,
    redis_url: str,
    velocidad: float,
    telefonia: bool,
    customer_id: str,
    agent_id: str,
) -> int:
    directorio = RAIZ_AUDIO / scenario_id
    if not directorio.exists():
        print(f"No hay audio para '{scenario_id}'. Ejecutar `make audio`.", file=sys.stderr)
        return 1
    if not MODELO.exists():
        print("Falta el modelo de voz. Ejecutar `make models`.", file=sys.stderr)
        return 1

    call_id = f"call-{scenario_id}"
    adaptador = FileReplayAdapter(call_id, directorio, velocidad=velocidad, telefonia=telefonia)
    asr = SherpaStreamingASR(MODELO)
    bus = EventBus.desde_url(redis_url)

    pipeline = CallPipeline(
        call_id=call_id,
        customer_id=customer_id,
        agent_id=agent_id,
        asr=asr,
        bus=bus,
        ingress="file_replay",
        scenario_id=scenario_id,
    )

    canal = "telefonía 8 kHz" if telefonia else "micrófono 16 kHz"
    print(f"Reproduciendo {scenario_id} · {canal} · velocidad {velocidad}×")
    print(f"Abrir el portal en /llamadas/{call_id}\n")

    try:
        await pipeline.start(room=f"replay-{scenario_id}")
        async for frame in adaptador.frames():
            await pipeline.feed(frame)
        await pipeline.stop()
    finally:
        await adaptador.aclose()
        await bus.aclose()

    print("\nLlamada terminada.")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Reproduce un escenario como llamada en vivo.")
    p.add_argument("--scenario", default="disputa_cargo_no_reconocido")
    p.add_argument("--redis", default=os.environ.get("CEA_REDIS_URL", "redis://localhost:6380/0"))
    p.add_argument(
        "--velocidad",
        type=float,
        default=1.0,
        help="1.0 = tiempo real. Mayor acelera; se usa en tests.",
    )
    p.add_argument(
        "--telefonia",
        action="store_true",
        help="Degrada el audio a 8 kHz µ-law, como una llamada real.",
    )
    p.add_argument("--customer-id", default="CUS000001")
    p.add_argument("--agent-id", default="dev-ejecutivo")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    return asyncio.run(
        reproducir(
            args.scenario,
            redis_url=args.redis,
            velocidad=args.velocidad,
            telefonia=args.telefonia,
            customer_id=args.customer_id,
            agent_id=args.agent_id,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
