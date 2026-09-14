"""Qué sugerir y cuándo: la política del copiloto sobre la llamada en vivo."""

from .llamada import Llamada
from .politica import ENFRIAMIENTO_S, MINIMO_PALABRAS, Politica

__all__ = ["ENFRIAMIENTO_S", "MINIMO_PALABRAS", "Llamada", "Politica"]
