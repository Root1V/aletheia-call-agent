"""CLI del generador: `cea-seed`."""

from __future__ import annotations

import argparse
import sys

from .seed import DEFAULT_DSN, seed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cea-seed",
        description="Carga un dataset sintético reproducible de banca peruana en Postgres.",
    )
    parser.add_argument("--dsn", default=DEFAULT_DSN, help="Cadena de conexión a Postgres.")
    parser.add_argument(
        "--customers",
        type=int,
        default=150,
        help="Clientes de relleno además de los de los escenarios.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=2026,
        help="Semilla. La misma semilla produce exactamente el mismo dataset.",
    )
    args = parser.parse_args(argv)

    print(f"Cargando dataset (semilla {args.seed}) en {args.dsn.split('@')[-1]} ...")
    report = seed(args.dsn, extra_customers=args.customers, seed_value=args.seed)
    print(f"Listo: {report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
