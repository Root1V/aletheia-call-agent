"""Los tipos del portal y los contratos de Pydantic no pueden divergir.

El frontend mantiene a mano un espejo en TypeScript de `packages/contracts`.
Es una decisión consciente —evita un paso de generación en el build— pero abre
un riesgo: si alguien cambia un campo en Pydantic y no aquí, el error aparece en
tiempo de ejecución y no de compilación.

Esta prueba existe porque ese riesgo se materializó. `CaseClassified.proposed_type`
era obligatorio en Pydantic y anulable en TypeScript, y la llamada que se resuelve
sin abrir caso —el desenlace de la mayoría de las disputas— reventaba al publicar
el evento, dentro de una tarea, sin que el portal se enterase de nada.

Compara nombres de campo y anulabilidad, que es donde ocurre la deriva real.
No compara tipos: hacerlo exigiría un analizador de TypeScript, y el coste no
compensa para lo que queda por atrapar.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import UnionType
from typing import Union, get_args, get_origin

import pytest
from cea_contracts.events import Event

TYPES_TS = Path("apps/web/src/lib/types.ts")

pytestmark = pytest.mark.skipif(
    not TYPES_TS.exists(), reason="Sin el portal a la vista; se ejecuta desde la raíz del repo."
)


def _eventos_de_pydantic() -> dict[str, type]:
    """Los eventos del bus, indexados por su discriminador `type`.

    `Event` es una unión anotada con su discriminador, así que hay que desenvolver
    el `Annotated` antes de llegar a los modelos.
    """
    modelos = [m for m in get_args(Event) if hasattr(m, "model_fields")]
    if not modelos:  # Annotated[A | B | C, Field(discriminator=...)]
        modelos = [m for a in get_args(Event) for m in get_args(a) if hasattr(m, "model_fields")]
    assert modelos, "no se pudo desenvolver la unión de eventos"
    return {m.model_fields["type"].default: m for m in modelos}


_INTERFAZ = re.compile(r"export interface (\w+)\s*\{(.*?)\n\}", re.S)
_CAMPO = re.compile(r"^\s{2}(\w+)(\??):\s*(.+?);\s*$", re.M)
_DISCRIMINADOR = re.compile(r'^\s{2}type:\s*"([\w.]+)";', re.M)


def _eventos_de_typescript() -> dict[str, dict[str, bool]]:
    """Por evento, sus campos y si el portal los declara anulables."""
    fuente = TYPES_TS.read_text(encoding="utf-8")
    encontrados: dict[str, dict[str, bool]] = {}
    for _nombre, cuerpo in _INTERFAZ.findall(fuente):
        discriminador = _DISCRIMINADOR.search(cuerpo)
        if discriminador is None:
            continue
        campos = {}
        for campo, opcional, tipo in _CAMPO.findall(cuerpo):
            if campo == "type":
                continue
            campos[campo] = bool(opcional) or "null" in tipo.split("|")[-1]
        encontrados[discriminador.group(1)] = campos
    return encontrados


def _admite_none(anotacion) -> bool:
    """¿El campo acepta None?

    Hay que contemplar las DOS formas de unión: `typing.Optional[X]` produce
    `typing.Union`, y la sintaxis moderna `X | None` produce `types.UnionType`.
    Comprobar sólo una daba por obligatorios campos que sí son anulables, y la
    prueba se ponía roja sobre contratos correctos — que es la forma de que deje
    de leerse.
    """
    return get_origin(anotacion) in (Union, UnionType) and type(None) in get_args(anotacion)


# Campos comunes que el portal recibe pero no siempre declara: no son deriva.
_COMUNES = {"event_id"}


@pytest.mark.parametrize("tipo_de_evento", sorted(_eventos_de_typescript()))
def test_el_portal_declara_los_mismos_campos(tipo_de_evento: str) -> None:
    modelo = _eventos_de_pydantic().get(tipo_de_evento)
    assert modelo is not None, f"el portal declara '{tipo_de_evento}', que no existe en Pydantic"

    del_portal = set(_eventos_de_typescript()[tipo_de_evento])
    de_pydantic = set(modelo.model_fields) - {"type"} - _COMUNES

    inventados = del_portal - de_pydantic
    assert not inventados, f"campos que el portal espera y Pydantic no envía: {sorted(inventados)}"


@pytest.mark.parametrize("tipo_de_evento", sorted(_eventos_de_typescript()))
def test_la_anulabilidad_coincide(tipo_de_evento: str) -> None:
    """El caso exacto que se coló.

    Un campo que el portal pinta como opcional y Pydantic exige revienta al
    publicar el evento, dentro de la tarea del orquestador, y el portal se queda
    esperando algo que nunca llega.
    """
    modelo = _eventos_de_pydantic()[tipo_de_evento]
    discrepancias = []
    for campo, anulable_en_portal in _eventos_de_typescript()[tipo_de_evento].items():
        info = modelo.model_fields.get(campo)
        if info is None:
            continue
        anulable_en_pydantic = _admite_none(info.annotation)
        if anulable_en_portal and not anulable_en_pydantic:
            discrepancias.append(f"{campo}: el portal lo admite nulo y Pydantic lo exige")
    assert not discrepancias, "\n".join(discrepancias)
