"""Redacción sobre transcripción en vivo.

Un turno cerrado se puede analizar entero, pero un parcial llega a medias, y
ahí aparece un problema que el texto estático no tiene: mientras el cliente
dicta su tarjeta, las hipótesis intermedias contienen trozos del número que
todavía no alcanzan ningún patrón reconocible.

    "el número es cuatro, uno, uno"        -> 3 dígitos, no encaja en nada
    "el número es cuatro, uno, uno, uno"   -> 4 dígitos, tampoco
    ...
    (dieciséis dígitos después)            -> ahora sí: es una tarjeta

Si cada hipótesis se publicara tal cual, el número entero habría pasado por el
bus y por la pantalla cifra a cifra antes de que el detector pudiera
reconocerlo. Redactar sólo el resultado final no evita esa fuga.
"""

from __future__ import annotations

from .numeros import extraer_cadenas
from .redactor import Redaccion, redactar

# A partir de cuántas cifras seguidas se considera que alguien está dictando.
#
# Tres es bajo a propósito. El coste de equivocarse es que el ejecutivo no vea
# en vivo un trozo de frase con números —lo verá al cerrar el turno, un segundo
# después—; el coste de acertar tarde es un número de tarjeta publicado en el
# bus.
CIFRAS_QUE_SUGIEREN_DICTADO = 3


def parece_dictado_en_curso(texto: str) -> bool:
    """Si el texto termina en una tirada de cifras que aún está creciendo."""
    cadenas = extraer_cadenas(texto, minimo=CIFRAS_QUE_SUGIEREN_DICTADO)
    if not cadenas:
        return False
    ultima = cadenas[-1]
    # La tirada tiene que llegar hasta el final del texto: si después hay más
    # palabras, el dictado ya terminó y el detector normal puede juzgarlo.
    return ultima.fin >= len(texto.rstrip(" .,"))


def redactar_parcial(texto: str) -> Redaccion | None:
    """Redacta una hipótesis intermedia, o la retiene si hay un dictado en curso.

    Devolver `None` significa "no publiques esto todavía". El turno se verá
    completo y redactado en cuanto cierre.
    """
    if parece_dictado_en_curso(texto):
        return None
    return redactar(texto)
