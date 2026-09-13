#!/usr/bin/env python
"""Descarga los modelos de voz a `models/`.

Los pesos no se versionan en el repositorio. Más allá del tamaño, cada modelo
trae su propia licencia —distinta de la Apache-2.0 del proyecto— y vendorizarlo
mezclaría obligaciones que conviene mantener separadas. Descargándolo, el
código sigue siendo Apache-2.0 y el modelo conserva la suya, que este script
muestra al instalar en vez de esconderla en un archivo que nadie abre.

    uv run python scripts/fetch_models.py            # los necesarios
    uv run python scripts/fetch_models.py --all      # también los opcionales
    uv run python scripts/fetch_models.py --licenses # sólo mostrar licencias
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

sys.path.insert(0, "services/asr/src")

from cea_asr.models import MODELOS, ModeloDeVoz, resumen_de_licencias  # noqa: E402

RAIZ_MODELOS = Path("models")
# Lo mínimo para que la transcripción en vivo funcione.
NECESARIOS = ("asr-es-streaming",)


def _descargar(modelo: ModeloDeVoz, destino: Path) -> None:
    print(f"  descargando {modelo.nombre} ({modelo.tamano_mb} MB)…")
    with tempfile.NamedTemporaryFile(suffix=".tar.bz2", delete=False) as tmp:
        ruta_tmp = Path(tmp.name)
    try:
        urllib.request.urlretrieve(modelo.url, ruta_tmp)
        with tarfile.open(ruta_tmp, "r:bz2") as tar:
            # `filter="data"` rechaza rutas absolutas y con ".." dentro del
            # tar. Sin él, un archivo manipulado puede escribir fuera del
            # directorio de destino.
            tar.extractall(destino.parent, filter="data")
    finally:
        ruta_tmp.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Descarga de modelos de voz.")
    p.add_argument("--all", action="store_true", help="Incluye los modelos opcionales.")
    p.add_argument("--force", action="store_true", help="Vuelve a descargar aunque exista.")
    p.add_argument("--licenses", action="store_true", help="Sólo muestra las licencias.")
    args = p.parse_args(argv)

    if args.licenses:
        print(resumen_de_licencias())
        return 0

    claves = tuple(MODELOS) if args.all else NECESARIOS
    RAIZ_MODELOS.mkdir(exist_ok=True)

    for clave in claves:
        modelo = MODELOS[clave]
        destino = RAIZ_MODELOS / modelo.directorio
        print(f"\n{clave}  [{modelo.licencia}]")

        if destino.exists() and not args.force:
            print(f"  ya está en {destino}")
            continue
        if destino.exists():
            shutil.rmtree(destino)

        try:
            _descargar(modelo, destino)
        except Exception as exc:  # noqa: BLE001 - queremos el motivo en pantalla
            print(f"  FALLÓ: {exc}", file=sys.stderr)
            return 1
        print(f"  listo en {destino}")

    print()
    print("=" * 72)
    print(resumen_de_licencias())
    print("=" * 72)
    print(
        "Los modelos NO son Apache-2.0 como el resto del proyecto. Revisar sus\n"
        "términos con el área legal antes de un despliegue en producción."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
