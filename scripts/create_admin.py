#!/usr/bin/env python
"""Crea o actualiza un usuario del portal.

Es el único camino de alta: no hay endpoint público de registro. En una
herramienta interna de un banco no existe caso de uso para el auto-registro, y
quitarlo elimina de un plumazo la enumeración de cuentas, la confirmación por
correo y la recuperación abierta como superficies de ataque.

    uv run python scripts/create_admin.py --username carlos --name "Carlos Ruiz"

Sin --password genera una contraseña fuerte y la imprime UNA sola vez. Eso es
preferible a que quien ejecuta el script elija "admin1234" por comodidad.
"""

from __future__ import annotations

import argparse
import getpass
import secrets
import sys
import uuid

import psycopg

sys.path.insert(0, "apps/api/src")

from api.auth import hash_password  # noqa: E402

DSN_POR_DEFECTO = "postgresql://cea:cea_dev@localhost:5432/cea"
ROLES_VALIDOS = {"ejecutivo", "supervisor", "admin"}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Alta de usuarios del portal.")
    p.add_argument("--dsn", default=DSN_POR_DEFECTO)
    p.add_argument("--username", required=True)
    p.add_argument("--name", required=True, help="Nombre completo, como se muestra en el portal.")
    p.add_argument("--email")
    p.add_argument(
        "--roles",
        default="admin,supervisor,ejecutivo",
        help=f"Separados por coma. Válidos: {', '.join(sorted(ROLES_VALIDOS))}",
    )
    p.add_argument(
        "--password",
        help="Si se omite, se pide por consola o se genera una fuerte.",
    )
    p.add_argument(
        "--generate-password",
        action="store_true",
        help="Genera una contraseña fuerte y la imprime una sola vez.",
    )
    args = p.parse_args(argv)

    roles = [r.strip() for r in args.roles.split(",") if r.strip()]
    invalidos = set(roles) - ROLES_VALIDOS
    if invalidos:
        p.error(f"Roles desconocidos: {', '.join(sorted(invalidos))}")

    generada: str | None = None
    if args.password:
        password = args.password
    elif args.generate_password:
        generada = password = secrets.token_urlsafe(18)
    else:
        password = getpass.getpass("Contraseña: ")
        if password != getpass.getpass("Repetir contraseña: "):
            print("Las contraseñas no coinciden.", file=sys.stderr)
            return 1

    if len(password) < 12:
        print("La contraseña debe tener al menos 12 caracteres.", file=sys.stderr)
        return 1

    with psycopg.connect(args.dsn) as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO users (user_id, username, email, full_name, password_hash, roles)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (username) DO UPDATE
               SET full_name = EXCLUDED.full_name,
                   email = EXCLUDED.email,
                   password_hash = EXCLUDED.password_hash,
                   roles = EXCLUDED.roles,
                   is_active = true
            RETURNING user_id, (xmax = 0) AS creado
            """,
            (
                f"usr_{uuid.uuid4().hex[:12]}",
                args.username,
                args.email,
                args.name,
                hash_password(password),
                roles,
            ),
        )
        fila = cur.fetchone()
        conn.commit()

    accion = "creado" if fila[1] else "actualizado"
    print(f"Usuario {accion}: {args.username} ({args.name}) — roles: {', '.join(roles)}")
    if generada:
        print()
        print(f"  Contraseña generada: {generada}")
        print("  Se muestra una sola vez: guardarla ahora en el gestor de contraseñas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
