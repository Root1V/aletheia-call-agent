#!/usr/bin/env python
"""¿Encuentra la búsqueda el pasaje correcto, y lo pone primero?

    uv run python evals/runners/rag_eval.py [--rerank | --comparar]

El conjunto de consultas está escrito **como habla un cliente por teléfono**, no
como está redactado el documento. Esa distancia es el problema real: el
tarifario dice "comisión por disposición de efectivo" y el cliente dice "sacar
plata del cajero". Una evaluación construida parafraseando el propio documento
mide lo fácil y sale siempre bien.

Dos métricas, y la segunda importa más:

- **Recall@5**: si el pasaje correcto entró entre los cinco que ve el modelo.
  Por debajo de esto la sugerencia no puede ser correcta ni por casualidad.
- **Acierto@1**: si quedó PRIMERO. Con cinco pasajes en el prompt, el que
  encabeza es el que el modelo cita; los demás son contexto.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import statistics
import sys
import time
from dataclasses import dataclass

import psycopg
from cea_llm import AxoniumProvider, CredencialesFaltantes, obtener_ajustes
from cea_rag import buscar, embeber_consulta, reordenar
from psycopg.rows import dict_row

DSN = os.environ.get("CEA_DATABASE_URL", "postgresql://cea:cea_dev@localhost:5432/cea")


@dataclass(frozen=True)
class Caso:
    consulta: str
    esperado: str
    """El `chunk_id` que responde la pregunta."""


# Una consulta por trozo de la base, en el registro en que llegan por teléfono.
CASOS: tuple[Caso, ...] = (
    Caso(
        "¿Cuánto me cobran por sacar plata del cajero con la tarjeta de crédito?",
        "tarifario-tc-2026#001",
    ),
    Caso("Me apareció un cobro que dice COMISION MEMBRESIA, ¿eso qué es?", "tarifario-tc-2026#000"),
    Caso("Se me perdió la tarjeta, ¿cuánto cuesta que me manden otra?", "tarifario-tc-2026#002"),
    Caso("Quiero anular mi tarjeta ahora mismo porque me la robaron", "proc-tarjetas-2026#001"),
    Caso(
        "¿Por qué me rechazaron la compra si yo tengo saldo suficiente?", "proc-tarjetas-2026#003"
    ),
    Caso(
        "En mi estado de cuenta sale un nombre raro que no es la tienda donde compré",
        "proc-tarjetas-2026#000",
    ),
    Caso(
        "Ustedes me bloquearon una compra sin avisarme, ¿por qué hacen eso?",
        "proc-tarjetas-2026#002",
    ),
    Caso(
        "Quiero comprar más por internet pero no me deja pasar de cierto monto",
        "proc-tarjetas-2026#004",
    ),
    Caso(
        "¿Cuánto se demoran en darme una respuesta sobre esto que estoy reportando?",
        "proc-reclamos-2026#001",
    ),
    Caso("¿Me van a devolver el dinero de una vez o tengo que esperar?", "proc-reclamos-2026#003"),
    Caso("Si no me contestan voy a ir a la SBS y a Indecopi", "proc-reclamos-2026#004"),
    Caso(
        "Esto que le estoy diciendo, ¿cuenta como una queja formal o es solo una consulta?",
        "proc-reclamos-2026#000",
    ),
    Caso(
        "¿Cómo hago para saber después en qué quedó lo que estoy reportando?",
        "proc-reclamos-2026#002",
    ),
)


@dataclass
class Resultado:
    aciertos_en_1: int = 0
    aciertos_en_5: int = 0
    latencias: list[float] = None  # type: ignore[assignment]
    fallos: list[tuple[str, str, str]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.latencias = []
        self.fallos = []

    def informe(self, total: int, etiqueta: str) -> str:
        p50 = statistics.median(self.latencias) if self.latencias else 0
        p90 = (
            statistics.quantiles(self.latencias, n=10)[8]
            if len(self.latencias) >= 10
            else max(self.latencias, default=0)
        )
        return (
            f"  {etiqueta:22} acierto@1 {self.aciertos_en_1}/{total}"
            f" ({self.aciertos_en_1 / total:5.0%})"
            f"   recall@5 {self.aciertos_en_5}/{total} ({self.aciertos_en_5 / total:5.0%})"
            f"   {p50:5.0f} ms p50 · {p90:5.0f} ms p90"
        )


async def _correr(cur, proveedor, *, con_rerank: bool, devolver: int) -> Resultado:
    r = Resultado()

    async def reordenador(consulta: str, pasajes, cuantos: int):
        return await reordenar(proveedor, consulta, pasajes, devolver=cuantos)

    for caso in CASOS:
        vector = await embeber_consulta(proveedor, caso.consulta)
        inicio = time.perf_counter()
        pasajes = await buscar(
            cur,
            caso.consulta,
            vector,
            candidatos=30,
            devolver=devolver,
            reordenador=reordenador if con_rerank else None,
        )
        r.latencias.append((time.perf_counter() - inicio) * 1000)

        ids = [p.chunk_id for p in pasajes]
        if ids and ids[0] == caso.esperado:
            r.aciertos_en_1 += 1
        if caso.esperado in ids:
            r.aciertos_en_5 += 1
        else:
            r.fallos.append((caso.consulta, caso.esperado, ids[0] if ids else "—"))
    return r


async def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Evalúa la recuperación de la base de conocimiento.")
    p.add_argument("--rerank", action="store_true", help="Sólo con reordenador.")
    p.add_argument("--comparar", action="store_true", help="Con y sin, uno detrás de otro.")
    p.add_argument("--devolver", type=int, default=5)
    args = p.parse_args(argv)

    if not obtener_ajustes().hay_credenciales:
        print(CredencialesFaltantes().args[0], file=sys.stderr)
        return 1

    proveedor = AxoniumProvider()
    # Primera petición en frío: el arranque del modelo no es latencia de
    # búsqueda y contarlo en el p50 de trece casos lo distorsiona entero.
    await embeber_consulta(proveedor, "calentamiento")

    modos = [False, True] if args.comparar else [bool(args.rerank)]
    print(f"\nBase de conocimiento · {len(CASOS)} consultas, top-{args.devolver}\n")

    async with await psycopg.AsyncConnection.connect(DSN, row_factory=dict_row) as conn:
        async with conn.cursor() as cur:
            for con_rerank in modos:
                r = await _correr(cur, proveedor, con_rerank=con_rerank, devolver=args.devolver)
                print(r.informe(len(CASOS), "RRF + reordenador" if con_rerank else "RRF solo"))
                for consulta, esperado, primero in r.fallos:
                    print(f"      ✗ «{consulta[:62]}»")
                    print(f"        esperaba {esperado} · devolvió {primero} primero")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
