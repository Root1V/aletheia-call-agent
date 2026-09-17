"""Sugerencia de respuesta con citación obligatoria y verificación de cifras."""

from .atribucion import APORTE_MINIMO, TERMINOS_MINIMOS, atribuir
from .cifras import Cantidad, Verificacion, extraer_cantidades, verificar
from .contexto import resumir
from .guardarrailes import COBERTURA_MINIMA, Bloqueo, Resultado, evaluar
from .prompt import Contexto, construir
from .sugerencia import Sugerencia, generar
from .tono import UMBRAL, instruccion

__all__ = [
    "APORTE_MINIMO",
    "COBERTURA_MINIMA",
    "Bloqueo",
    "Cantidad",
    "Contexto",
    "Resultado",
    "TERMINOS_MINIMOS",
    "Sugerencia",
    "UMBRAL",
    "Verificacion",
    "atribuir",
    "construir",
    "evaluar",
    "extraer_cantidades",
    "instruccion",
    "resumir",
    "generar",
    "verificar",
]
