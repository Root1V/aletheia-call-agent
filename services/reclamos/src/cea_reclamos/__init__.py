"""Reclamos y requerimientos bajo la Ley 31763.

Las reglas deciden y el modelo redacta. Nunca al revés: clasificar mal un
reclamo priva al usuario del plazo legal y de la vía de escalamiento a la SBS,
y eso tiene que poder explicarse con la regla que se aplicó.
"""

from .justificacion import Justificacion, contradice, redactar
from .ley31763 import (
    CONFIANZA_AFECTACION,
    CONFIANZA_ESCALAMIENTO,
    Desenlace,
    Dictamen,
    clasificar,
)
from .plazo import DIAS_DE_PLAZO, EstadoDelPlazo, Plazo, estado, vencimiento
from .senales import Hallazgo, Marca, Senales, extraer

__all__ = [
    "CONFIANZA_AFECTACION",
    "CONFIANZA_ESCALAMIENTO",
    "DIAS_DE_PLAZO",
    "Desenlace",
    "Dictamen",
    "EstadoDelPlazo",
    "Hallazgo",
    "Justificacion",
    "Marca",
    "Plazo",
    "Senales",
    "clasificar",
    "contradice",
    "estado",
    "extraer",
    "redactar",
    "vencimiento",
]
