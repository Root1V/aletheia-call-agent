"""Extracción de cifras citables.

Es el control que impide que el copiloto invente una tarifa. El texto de un
documento se puede parafrasear; una comisión, no. Estas cifras se guardan
aparte, en forma estructurada, y toda cantidad que el modelo emita se contrasta
contra ellas antes de mostrarse.

No es una precaución teórica: en la primera generación real contra la
plataforma, el modelo de 20B escribió "una tarifa legítima por los 6 viajes"
cuando eran 189 soles de UN cargo y seis compras previas sin relación con el
importe.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Importe en soles: "S/ 45.00", "S/ 1,450.00".
_SOLES = re.compile(r"S/\s*([\d]{1,3}(?:[, ]\d{3})*(?:\.\d{2})?)")
# Porcentaje: "5.00%", "2.5 %".
_PORCENTAJE = re.compile(r"([\d]+(?:\.\d+)?)\s*%")
# Plazo en días hábiles, escrito en cifras o en palabras.
_DIAS = re.compile(
    r"(?:(\d+)|quince|treinta|diez|siete|cinco)\s*\(?\d*\)?\s*d[ií]as\s+h[aá]biles", re.I
)

_PALABRA_A_NUMERO = {"quince": 15, "treinta": 30, "diez": 10, "siete": 7, "cinco": 5}

# Filas de tabla markdown: | concepto | valor |
_FILA = re.compile(r"^\|\s*(?P<concepto>[^|]+?)\s*\|\s*(?P<valor>[^|]+?)\s*\|\s*$", re.M)


@dataclass(slots=True, frozen=True)
class Hecho:
    fact_id: str
    document_id: str
    clave: str
    valor: float
    unidad: str
    nota: str
    product_code: str | None = None


def _a_numero(texto: str) -> float | None:
    limpio = texto.replace(",", "").replace(" ", "")
    try:
        return float(limpio)
    except ValueError:
        return None


def _clave(concepto: str) -> str:
    """Normaliza un concepto a una clave estable."""
    import unicodedata

    base = unicodedata.normalize("NFKD", concepto.lower()).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "_", base).strip("_")[:60]


def extraer(document_id: str, contenido: str) -> list[Hecho]:
    """Saca de un documento todas las cifras que podrían citarse.

    Se extrae de más a propósito. Un hecho sobrante no hace daño —nadie lo
    consultará— pero una comisión ausente de la tabla convierte la verificación
    en un cheque en blanco: el modelo la dice, el verificador no la encuentra y
    hay que decidir entre bloquear una respuesta correcta o dejar pasar una
    inventada.
    """
    hechos: list[Hecho] = []
    vistos: set[str] = set()

    def añadir(clave: str, valor: float, unidad: str, nota: str) -> None:
        if clave in vistos:
            return
        vistos.add(clave)
        hechos.append(
            Hecho(
                fact_id=f"{document_id}:{clave}",
                document_id=document_id,
                clave=clave,
                valor=valor,
                unidad=unidad,
                nota=" ".join(nota.split())[:200],
            )
        )

    # Tablas: el concepto está en la primera columna y el valor en la segunda.
    for m in _FILA.finditer(contenido):
        concepto, valor = m.group("concepto"), m.group("valor")
        if concepto.strip("-: ") == "" or concepto.lower().strip() in {"producto", "concepto"}:
            continue
        if soles := _SOLES.search(valor):
            if (n := _a_numero(soles.group(1))) is not None:
                añadir(_clave(concepto), n, "pen", f"{concepto}: {valor}")
        elif pct := _PORCENTAJE.search(valor):
            if (n := _a_numero(pct.group(1))) is not None:
                añadir(_clave(concepto), n, "porcentaje", f"{concepto}: {valor}")

    # Frases sueltas: se toma la oración entera como nota para que un revisor
    # pueda juzgar el contexto sin abrir el documento.
    for oracion in re.split(r"(?<=[.:])\s+", contenido):
        if len(oracion) > 300:
            continue
        for m in _SOLES.finditer(oracion):
            if (n := _a_numero(m.group(1))) is not None:
                añadir(_clave(f"{oracion[:40]}_{n}"), n, "pen", oracion)
        for m in _PORCENTAJE.finditer(oracion):
            if (n := _a_numero(m.group(1))) is not None:
                añadir(_clave(f"{oracion[:40]}_{n}pct"), n, "porcentaje", oracion)
        if m := _DIAS.search(oracion):
            crudo = m.group(1)
            n = (
                float(crudo)
                if crudo
                else float(_PALABRA_A_NUMERO.get(m.group(0).split()[0].lower(), 0))
            )
            if n:
                añadir(_clave(f"plazo_{oracion[:34]}"), n, "dias_habiles", oracion)

    return hechos
