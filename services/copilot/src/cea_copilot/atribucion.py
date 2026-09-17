"""Qué pasaje respalda realmente la frase que se va a decir.

Citar el primer pasaje recuperado es decorar, no citar. Muchas sugerencias del
flujo de reclamos se construyen ENTERAS con los datos de la llamada —el
comercio real, la fecha, las compras previas— y no deben nada a ningún
documento; acompañarlas de una referencia al tarifario le dice al ejecutivo que
hay respaldo documental donde no lo hay, y es él quien responde si el cliente
pregunta de dónde sale.

La atribución es léxica y deliberadamente tosca. Una atribución sofisticada
—otro modelo juzgando qué frase vino de dónde— sería más fina y menos
auditable, y este control existe precisamente para poder explicarse ante
alguien que pregunta por qué se mostró lo que se mostró.
"""

from __future__ import annotations

from cea_rag import Pasaje

from .guardarrailes import normalizar

# Cuánto de lo que la frase NO sacó de la llamada tiene que venir del pasaje.
#
# La proporción se mide sobre los términos de la frase que no están ya en los
# datos de la llamada. Esa resta es lo que hace útil el umbral: sin ella, el
# vocabulario compartido —"tarjeta", "cargo", "comercio", "cuenta", que están a
# la vez en el contexto y en todos los documentos— basta para atribuirle una
# fuente documental a cualquier frase.
#
# Un quinto de los términos restantes es un solapamiento que ya no ocurre por
# casualidad: son palabras específicas del documento —"membresía", "aniversario",
# "procesador", "hábiles"— que la frase sólo pudo tomar de ahí.
APORTE_MINIMO = 0.20

# Y cuántos términos propios como mínimo, en números absolutos.
#
# La proporción sola engaña cuando el denominador es diminuto. Medido sobre una
# llamada real: a una frase hecha entera con los datos de la llamada le
# quedaban dos términos propios —"corresponde" y "mismo"—, uno de los cuales
# aparecía en el tarifario, y salía atribuida al tarifario con un 50% de
# aporte. Dos palabras corrientes no son una fuente.
#
# El corolario es deliberado: una frase que no dice nada más allá de los datos
# de la llamada NO PUEDE quedar atribuida a ningún documento, porque no está
# haciendo ninguna afirmación documental que respaldar.
TERMINOS_MINIMOS = 3

# Cuántas citas se muestran.
#
# Dos. El ejecutivo no va a abrir cinco documentos con el cliente al teléfono, y
# una lista larga de referencias se lee como ninguna.
MAXIMO_CITAS = 2


def atribuir(
    sugerencia: str,
    pasajes: tuple[Pasaje, ...],
    *,
    datos_de_la_llamada: str = "",
) -> tuple[Pasaje, ...]:
    """Los pasajes que de verdad aportaron términos a la frase, mejor primero.

    Los términos que la frase ya podía tomar de los datos de la llamada se
    descuentan antes de comparar: que "cargo", "comercio" y "tarjeta" aparezcan
    también en un documento no prueba que el documento se usara, sólo que el
    vocabulario bancario es el mismo en todas partes.

    Devuelve una tupla vacía cuando la frase sale sólo de los datos de la
    llamada. Eso NO es un fallo: es el caso más frecuente del flujo de reclamos,
    y es información que el portal debe mostrar como tal —"según los datos de la
    llamada"— en lugar de inventarle una fuente documental.
    """
    terminos = set(normalizar(sugerencia)) - set(normalizar(datos_de_la_llamada))
    if not terminos:
        return ()

    puntuados = []
    for p in pasajes:
        comunes = terminos & set(normalizar(p.contenido))
        aporte = len(comunes) / len(terminos)
        if len(comunes) >= TERMINOS_MINIMOS and aporte >= APORTE_MINIMO:
            puntuados.append((aporte, p))

    puntuados.sort(key=lambda par: par[0], reverse=True)
    return tuple(p for _aporte, p in puntuados[:MAXIMO_CITAS])
