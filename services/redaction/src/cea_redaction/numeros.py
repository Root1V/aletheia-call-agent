"""Números dictados en voz alta.

Es la pieza sin la cual toda la redacción es teatro.

Nadie deletrea su DNI escribiéndolo: lo dice. Y el reconocedor transcribe lo
que oye, así que "45678912" llega al sistema como:

    "mi DNI es cuatro, cinco, seis, siete, ocho, nueve, uno, dos"

Un detector de PII de biblioteca —Presidio, una expresión regular, un NER—
busca ocho dígitos seguidos y no encuentra NADA. No falla ni avisa: informa
cero coincidencias y el número queda en claro en la base de datos. Es el peor
modo de fallo imaginable, porque parece que el control funciona.

Este módulo convierte esas secuencias habladas en dígitos y conserva la
correspondencia con las palabras originales, para poder tachar exactamente las
que hay que tachar.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# Sólo dígitos sueltos.
#
# Deliberadamente NO se incluyen números compuestos como "ciento ochenta y
# nueve". Eso es un importe, no un identificador, y convertirlo produciría
# falsos positivos que tacharían el monto que el ejecutivo necesita leer en voz
# alta. Quien dicta un documento lo hace cifra por cifra.
DIGITOS: dict[str, str] = {
    "cero": "0",
    "uno": "1",
    "una": "1",
    "dos": "2",
    "tres": "3",
    "cuatro": "4",
    "cinco": "5",
    "seis": "6",
    "siete": "7",
    "ocho": "8",
    "nueve": "9",
    # Variantes que devuelve el reconocedor con audio telefónico.
    "un": "1",
    "o": "0",
}

# Pares que se dictan juntos con frecuencia al leer tarjetas.
DECENAS: dict[str, str] = {
    "diez": "10",
    "once": "11",
    "doce": "12",
    "trece": "13",
    "catorce": "14",
    "quince": "15",
    "dieciseis": "16",
    "diecisiete": "17",
    "dieciocho": "18",
    "diecinueve": "19",
    "veinte": "20",
}

_PALABRA = re.compile(r"\w+|\S", re.UNICODE)


def _normalizar(palabra: str) -> str:
    return unicodedata.normalize("NFKD", palabra.lower()).encode("ascii", "ignore").decode("ascii")


@dataclass(slots=True, frozen=True)
class Token:
    texto: str
    inicio: int
    fin: int


@dataclass(slots=True)
class CadenaDeDigitos:
    """Una tirada de dígitos dictados, con su origen en el texto.

    `digitos` es la forma normalizada sobre la que trabajan los detectores;
    `inicio` y `fin` marcan el tramo del texto original que hay que tachar si
    resulta ser un dato sensible.
    """

    digitos: str
    inicio: int
    fin: int
    posiciones: list[int]
    """Índice de carácter donde empieza cada dígito. Permite tachar tramos
    parciales, como los últimos cuatro de una tarjeta."""

    def tramo(self, desde: int, hasta: int) -> tuple[int, int]:
        """Traduce un rango de dígitos a un rango de caracteres del original."""
        if not self.posiciones:
            return self.inicio, self.fin
        desde = max(0, min(desde, len(self.posiciones) - 1))
        hasta = max(desde + 1, min(hasta, len(self.posiciones)))
        inicio = self.posiciones[desde]
        fin = self.fin if hasta >= len(self.posiciones) else self.posiciones[hasta]
        return inicio, fin


def tokenizar(texto: str) -> list[Token]:
    return [Token(m.group(), m.start(), m.end()) for m in _PALABRA.finditer(texto)]


def extraer_cadenas(texto: str, *, minimo: int = 6) -> list[CadenaDeDigitos]:
    """Encuentra las secuencias de dígitos dictados de al menos `minimo` cifras.

    El mínimo evita convertir menciones triviales: "tengo dos tarjetas" no es
    un identificador. Seis cifras es el suelo por debajo del cual ningún
    documento peruano ni ninguna tarjeta cabe.

    También reconoce dígitos ya escritos, porque un mismo turno puede mezclar
    ambas formas: "mi DNI 45678912" y "cuatro cinco seis..." conviven según lo
    que el reconocedor haya decidido.
    """
    tokens = tokenizar(texto)
    cadenas: list[CadenaDeDigitos] = []

    actual: list[str] = []
    posiciones: list[int] = []
    inicio = fin = 0

    def cerrar() -> None:
        nonlocal actual, posiciones, inicio, fin
        if len("".join(actual)) >= minimo:
            cadenas.append(CadenaDeDigitos("".join(actual), inicio, fin, list(posiciones)))
        actual = []
        posiciones = []

    for token in tokens:
        palabra = _normalizar(token.texto)
        valor: str | None = None

        if palabra.isdigit():
            valor = palabra
        elif palabra in DIGITOS:
            valor = DIGITOS[palabra]
        elif palabra in DECENAS:
            valor = DECENAS[palabra]

        if valor is None:
            # Comas y "y" no rompen la cadena: "cuatro, cinco y seis" es una
            # sola tirada dictada, y partirla en tres impediría reconocer el
            # documento completo.
            if token.texto in {",", "-", "y", "Y"} and actual:
                continue
            cerrar()
            continue

        if not actual:
            inicio = token.inicio
        # Cada dígito del token apunta al mismo inicio: si el reconocedor
        # escribió "45" como un token, ambos dígitos se tachan juntos.
        posiciones.extend([token.inicio] * len(valor))
        actual.append(valor)
        fin = token.fin

    cerrar()
    return cadenas
