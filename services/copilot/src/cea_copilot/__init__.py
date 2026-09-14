"""Sugerencia de respuesta con citación obligatoria y verificación de cifras."""

from .cifras import Cantidad, Verificacion, extraer_cantidades, verificar
from .guardarrailes import COBERTURA_MINIMA, Bloqueo, Resultado, evaluar
from .prompt import Contexto, construir
from .sugerencia import Sugerencia, generar

__all__ = [
    "COBERTURA_MINIMA",
    "Bloqueo",
    "Cantidad",
    "Contexto",
    "Resultado",
    "Sugerencia",
    "Verificacion",
    "construir",
    "evaluar",
    "extraer_cantidades",
    "generar",
    "verificar",
]
