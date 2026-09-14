"""Adaptación de la sugerencia al estado emocional del cliente.

Es la parte del producto que se pidió desde el principio: no sólo qué
responder, sino cómo responderlo según cómo esté el cliente. Se implementa como
una línea añadida al prompt y NO como un modelo aparte, porque el ajuste que
hace falta es de registro —reconocer antes de explicar, o explicar paso a
paso— y eso es exactamente lo que un modelo de lenguaje sabe hacer.

Dos límites deliberados:

1. Sólo se adapta a partir de un umbral. Una frustración medida al 30% está
   dentro del ruido de cualquier motor de emoción, y disculparse con alguien
   que no está molesto suena a guion y molesta de verdad.
2. Nunca cambia QUÉ se dice, sólo CÓMO. Los hechos y las cifras salen del
   material y de los guardarraíles; la emoción no puede añadir una promesa ni
   ablandar una cifra.
"""

from __future__ import annotations

from cea_contracts import EmotionLabel

# Por debajo de esto no se adapta nada.
#
# El motor de emoción entrega valores calibrados, así que 0.55 significa
# literalmente "más probable que no". Adaptarse por debajo de esa línea es
# reaccionar al ruido.
UMBRAL = 0.55

_INSTRUCCIONES: dict[EmotionLabel, str] = {
    EmotionLabel.FRUSTRACION: (
        "El cliente está molesto. Reconoce la molestia en pocas palabras y pasa "
        "enseguida al hecho concreto que resuelve su caso. Reconocer la molestia "
        "no es darle la razón: nada de «tiene razón», «es un error nuestro» ni "
        "disculpas en nombre del banco por algo que todavía no está determinado. "
        "Nada de fórmulas de cortesía largas."
    ),
    EmotionLabel.CONFUSION: (
        "El cliente no está entendiendo. Explica un solo hecho por frase, en orden, "
        "empezando por el dato más concreto (el comercio, la fecha, el monto). "
        "Evita términos del banco que el cliente no usa."
    ),
    EmotionLabel.URGENCIA: (
        "El cliente tiene prisa. Da primero la respuesta y después el detalle, "
        "en el menor número de palabras posible."
    ),
    EmotionLabel.SATISFACCION: (
        "El cliente está receptivo. Mantén un tono cordial y breve; no alargues."
    ),
}


def instruccion(scores: dict[EmotionLabel, float] | None) -> tuple[str | None, EmotionLabel | None]:
    """Instrucción de tono y la emoción que la justifica.

    Devuelve ambas cosas porque la emoción viaja al evento
    `suggestion.completed`: el portal muestra a qué estado se adaptó la
    sugerencia, y sin eso el ejecutivo no puede juzgar si el ajuste tenía
    sentido ni la evaluación puede medirlo después.
    """
    if not scores:
        return None, None
    etiqueta, valor = max(scores.items(), key=lambda kv: kv[1])
    if valor < UMBRAL or etiqueta is EmotionLabel.NEUTRAL:
        return None, None
    texto = _INSTRUCCIONES.get(etiqueta)
    return (texto, etiqueta) if texto else (None, None)
