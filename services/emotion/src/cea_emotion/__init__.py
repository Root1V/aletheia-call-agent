"""Estado emocional del cliente a partir de señales prosódicas."""

from .baseline import VENTANAS_DE_CALENTAMIENTO, LineaBase
from .engine import (
    CONFIANZA_MINIMA,
    HOP_MS,
    VENTANA_MS,
    MotorDeEmocion,
    SeñalesConversacionales,
)
from .features import Descriptores, extraer

__all__ = [
    "CONFIANZA_MINIMA",
    "HOP_MS",
    "VENTANAS_DE_CALENTAMIENTO",
    "VENTANA_MS",
    "Descriptores",
    "LineaBase",
    "MotorDeEmocion",
    "SeñalesConversacionales",
    "extraer",
]
