"""Controles sobre lo que el copiloto propone decir.

Tres comprobaciones, todas deterministas. Que lo sean no es una limitación:
un control de cumplimiento tiene que dar el mismo resultado dos veces y poder
explicarse ante un auditor. "El verificador le dio 0.83" no es una respuesta
aceptable cuando la pregunta es por qué se mostró una tarifa que no existe.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum

from .cifras import Verificacion, verificar


class Bloqueo(StrEnum):
    SIN_RESPALDO_DOCUMENTAL = "sin_respaldo_documental"
    CIFRA_NO_VERIFICADA = "cifra_no_verificada"
    FRASE_PROHIBIDA = "frase_prohibida"
    INSTRUCCION_AL_EJECUTIVO = "instruccion_al_ejecutivo"
    VACIA = "vacia"


# Compromisos que un ejecutivo de banca no puede hacer por teléfono.
#
# No son cuestión de estilo: prometer una rentabilidad o garantizar una
# aprobación crea una expectativa exigible y expone al banco ante la SBS y ante
# Indecopi.
FRASES_PROHIBIDAS: tuple[tuple[str, str], ...] = (
    # Las alternativas cubren formas verbales, no sólo sustantivos: el modelo
    # escribe "le devolveremos", no "la devolución". Buscar sólo el sustantivo
    # deja pasar la promesa en la forma en que realmente se dice por teléfono.
    (
        r"\bgarantiz\w+\b.{0,30}\b(aprob|devolv|devoluci|extorn|reembols|rentabilidad|ganancia|retorno)",
        "garantía de aprobación, devolución o rentabilidad",
    ),
    (
        r"\b(le\s+)?asegur\w+\b.{0,30}\b(aprob|devolv|devoluci|extorn|reembols)",
        "aseguramiento de un resultado del reclamo",
    ),
    (
        r"\bsin\s+duda\b.{0,30}\b(aprob|devolv|extorn)",
        "certeza sobre un resultado no decidido",
    ),
    (
        r"\b(rentabilidad|ganancia)\s+(asegurad|garantizad)",
        "promesa de rentabilidad",
    ),
    (
        r"\ble\s+conviene\s+invertir\b",
        "asesoría de inversión personalizada",
    ),
    (
        r"\b(seguro|siempre)\s+(le\s+)?(devolver|extornar)",
        "promesa de extorno",
    ),
)

# Marcas de que el modelo escribió PARA el ejecutivo en vez de PARA el cliente.
#
# Observado en la primera prueba real: ante un prompt flojo, el modelo devolvió
# "Verificar si el cliente tiene historial de compras en inDrive". Una tarjeta
# que le dice al ejecutivo lo que ya sabe no vale nada, y leerla en voz alta
# sería absurdo.
MARCAS_DE_INSTRUCCION: tuple[str, ...] = (
    r"^\s*(verificar|confirmar|revisar|comprobar|indicar|solicitar|preguntar)\b",
    r"\bel\s+ejecutivo\s+(debe|deber[ií]a|tiene\s+que)\b",
    r"\bse\s+recomienda\s+(verificar|confirmar|revisar)\b",
)

# Proporción mínima de palabras de contenido de la sugerencia que deben
# aparecer en el material que se le dio al modelo.
#
# No mide veracidad, mide procedencia: una sugerencia cuyas palabras no están
# en ningún pasaje recuperado ni en los datos de la llamada se la inventó
# entera. El umbral es bajo a propósito —redactar exige palabras propias— y lo
# que atrapa es la respuesta construida de la nada.
COBERTURA_MINIMA = 0.45

_VACIAS = {
    "el",
    "la",
    "los",
    "las",
    "un",
    "una",
    "unos",
    "unas",
    "de",
    "del",
    "al",
    "a",
    "en",
    "y",
    "o",
    "que",
    "se",
    "su",
    "sus",
    "por",
    "para",
    "con",
    "como",
    "es",
    "son",
    "fue",
    "ha",
    "han",
    "le",
    "lo",
    "les",
    "este",
    "esta",
    "esto",
    "ese",
    "esa",
    "eso",
    "no",
    "si",
    "mas",
    "pero",
    "tambien",
    "muy",
    "ya",
    "desde",
    "hasta",
    "sobre",
    "usted",
    "nos",
    "me",
    "mi",
    "tu",
    "hay",
    "the",
    "and",
}


def _normalizar(texto: str) -> list[str]:
    base = unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode("ascii")
    return [p for p in re.sub(r"[^\w\s]", " ", base).split() if p not in _VACIAS and len(p) > 2]


@dataclass(slots=True, frozen=True)
class Resultado:
    aprobada: bool
    bloqueos: tuple[Bloqueo, ...]
    motivo: str
    cobertura: float
    cifras: Verificacion


def evaluar(
    sugerencia: str,
    *,
    contexto: str,
    hechos: list[tuple[float, str]],
    hay_pasajes: bool,
) -> Resultado:
    """Decide si la sugerencia puede mostrarse."""
    bloqueos: list[Bloqueo] = []
    motivos: list[str] = []

    limpia = sugerencia.strip()
    if not limpia:
        return Resultado(
            False, (Bloqueo.VACIA,), "el modelo no devolvió texto", 0.0, Verificacion((), ())
        )

    for patron, descripcion in FRASES_PROHIBIDAS:
        if re.search(patron, limpia, re.IGNORECASE):
            bloqueos.append(Bloqueo.FRASE_PROHIBIDA)
            motivos.append(descripcion)
            break

    for patron in MARCAS_DE_INSTRUCCION:
        if re.search(patron, limpia, re.IGNORECASE):
            bloqueos.append(Bloqueo.INSTRUCCION_AL_EJECUTIVO)
            motivos.append("está escrita para el ejecutivo, no para el cliente")
            break

    cifras = verificar(limpia, contexto, hechos)
    if not cifras.aprobada:
        bloqueos.append(Bloqueo.CIFRA_NO_VERIFICADA)
        motivos.append(cifras.motivo)

    palabras = _normalizar(limpia)
    disponibles = set(_normalizar(contexto))
    cobertura = sum(1 for p in palabras if p in disponibles) / len(palabras) if palabras else 0.0
    if not hay_pasajes or cobertura < COBERTURA_MINIMA:
        bloqueos.append(Bloqueo.SIN_RESPALDO_DOCUMENTAL)
        motivos.append(
            "no hay pasaje que la respalde"
            if not hay_pasajes
            else f"sólo el {cobertura:.0%} de sus términos aparece en el material recuperado"
        )

    return Resultado(
        aprobada=not bloqueos,
        bloqueos=tuple(dict.fromkeys(bloqueos)),
        motivo="; ".join(motivos),
        cobertura=round(cobertura, 3),
        cifras=cifras,
    )
