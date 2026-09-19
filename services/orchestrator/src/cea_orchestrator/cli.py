#!/usr/bin/env python
"""Proceso del orquestador: una tarea por llamada abierta.

    uv run cea-orchestrator

Se engancha al índice de llamadas del bus y atiende cada una en paralelo. No
tiene estado propio: todo lo que sabe lo lee del stream de la llamada, así que
reiniciarlo a mitad de una conversación lo devuelve al punto correcto sin
perder nada ni repetir sugerencias ya emitidas.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

from cea_bus import EventBus
from cea_llm import (
    AxoniumProvider,
    CredencialesFaltantes,
    asegurar_visibilidad_de_esperas,
    obtener_ajustes,
)
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from .llamada import Llamada

log = logging.getLogger("cea.orquestador")

# Una conexión por llamada simultánea, más margen. Las consultas del copiloto
# —búsqueda híbrida y cifras del tarifario— son cortas, pero se sostienen
# mientras dura la generación, que son cientos de milisegundos.
CONEXIONES_MAX = 8


async def servir(*, redis_url: str, dsn: str, reordenar: bool = True) -> int:
    # Una espera de la plataforma no puede ser invisible: sin esto, un 429 con
    # `Retry-After` de treinta segundos se ve como una sugerencia colgada.
    asegurar_visibilidad_de_esperas()

    if not obtener_ajustes().hay_credenciales:
        print(CredencialesFaltantes().args[0], file=sys.stderr)
        return 1

    bus = EventBus.desde_url(redis_url)
    proveedor = AxoniumProvider()
    pool = AsyncConnectionPool(
        dsn, min_size=1, max_size=CONEXIONES_MAX, open=False, kwargs={"row_factory": dict_row}
    )
    await pool.open(wait=True, timeout=10)

    tareas: dict[str, asyncio.Task] = {}
    log.info("Orquestador en marcha")

    try:
        # Desde el principio del índice: una llamada que ya estaba en curso
        # cuando arrancó este proceso también necesita copiloto.
        async for _ident, call_id in bus.llamadas(desde="0"):
            anterior = tareas.get(call_id)
            if anterior is not None and not anterior.done():
                # El mismo identificador otra vez significa que la llamada se
                # reinició —reproducir un escenario dos veces lo hace—. La
                # tarea anterior sigue leyendo un stream que ya se vació.
                anterior.cancel()

            llamada = Llamada(
                call_id, bus=bus, pool=pool, proveedor=proveedor, reordenar_pasajes=reordenar
            )
            tareas[call_id] = asyncio.create_task(_atender(llamada, call_id))
    except asyncio.CancelledError:
        pass
    finally:
        for tarea in tareas.values():
            tarea.cancel()
        await asyncio.gather(*tareas.values(), return_exceptions=True)
        await pool.close()
        await bus.aclose()
    return 0


async def _atender(llamada: Llamada, call_id: str) -> None:
    """Aísla el fallo de una llamada del resto.

    Sin esto, una excepción en una conversación tumbaría la tarea y dejaría al
    resto de ejecutivos sin copiloto sin que nadie lo notara hasta la siguiente
    sugerencia que no llega.
    """
    try:
        await llamada.atender()
    except asyncio.CancelledError:
        raise
    except Exception:  # noqa: BLE001
        log.exception("El copiloto falló en %s; las demás llamadas siguen", call_id)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Copiloto: sugerencias sobre las llamadas abiertas.")
    p.add_argument("--redis", default=os.environ.get("CEA_REDIS_URL", "redis://localhost:6380/0"))
    p.add_argument(
        "--dsn",
        default=os.environ.get("CEA_DATABASE_URL", "postgresql://cea:cea_dev@localhost:5432/cea"),
    )
    p.add_argument(
        "--sin-reordenador",
        action="store_true",
        help=(
            "Salta el cross-encoder. Ahorra ~260 ms por sugerencia a cambio de citar "
            "peor: sobre el conjunto de evaluación, el acierto en primera posición "
            "baja del 85% al 54%."
        ),
    )
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    try:
        return asyncio.run(
            servir(redis_url=args.redis, dsn=args.dsn, reordenar=not args.sin_reordenador)
        )
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
