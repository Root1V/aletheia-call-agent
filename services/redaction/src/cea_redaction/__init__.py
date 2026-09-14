"""Redacción de datos sensibles en transcripciones de llamadas.

El caso que justifica que esto exista como servicio propio y no como una
expresión regular suelta: nadie deletrea su DNI, lo dice. El reconocedor
transcribe "cuatro, cinco, seis, siete, ocho, nueve, uno, dos", y cualquier
detector de PII de biblioteca busca ocho dígitos seguidos y no encuentra nada.
No falla ni avisa: informa cero coincidencias mientras el número queda en claro
en la base de datos.
"""

from .detectores import Hallazgo, luhn
from .numeros import CadenaDeDigitos, extraer_cadenas
from .redactor import ETIQUETAS, Redaccion, redactar
from .streaming import parece_dictado_en_curso, redactar_parcial

__all__ = [
    "ETIQUETAS",
    "CadenaDeDigitos",
    "Hallazgo",
    "Redaccion",
    "extraer_cadenas",
    "luhn",
    "parece_dictado_en_curso",
    "redactar_parcial",
    "redactar",
]
