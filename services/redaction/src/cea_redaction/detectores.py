"""Detectores de datos sensibles del perímetro peruano.

Reglas deterministas y no un modelo, a propósito. Un control de cumplimiento
tiene que poder explicarse ante un auditor y dar el mismo resultado dos veces:
"el modelo lo clasificó como tarjeta con probabilidad 0.87" no es una respuesta
aceptable cuando la pregunta es por qué un PAN quedó en claro.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass

from cea_contracts import PIIKind

from .numeros import CadenaDeDigitos

# Prefijos válidos de RUC. El primero identifica el tipo de contribuyente.
PREFIJOS_RUC = ("10", "15", "16", "17", "20")

# Palabras que anuncian un código de seguridad. Sin este contexto, tres dígitos
# sueltos son cualquier cosa; con él, son un CVV.
CONTEXTO_CVV = re.compile(
    r"\b(c[oó]digo\s+(de\s+)?seguridad|cvv|cvc|c[oó]digo\s+verificador|"
    r"tres\s+d[ií]gitos\s+(de\s+)?atr[aá]s)\b",
    re.IGNORECASE,
)

CONTEXTO_DNI = re.compile(r"\b(dni|documento|identidad)\b", re.IGNORECASE)
CONTEXTO_TARJETA = re.compile(r"\b(tarjeta|visa|mastercard|n[uú]mero\s+completo)\b", re.IGNORECASE)


@dataclass(slots=True, frozen=True)
class Hallazgo:
    kind: PIIKind
    inicio: int
    fin: int
    motivo: str
    """Por qué se marcó. Va al log de auditoría: sin esto, una redacción
    discutida no se puede defender ni corregir."""


def luhn(numero: str) -> bool:
    """Validación de Luhn.

    Es lo que separa un número de tarjeta real de dieciséis cifras cualesquiera.
    Sin esta comprobación, cualquier tirada larga de dígitos —un número de
    pedido, un código de operación— se tacharía como si fuera una tarjeta, y
    una redacción que se come datos legítimos se termina desactivando entera.
    """
    if not numero.isdigit() or len(numero) < 12:
        return False
    total = 0
    for i, c in enumerate(reversed(numero)):
        d = int(c)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _subcadenas(digitos: str, longitud: int) -> Iterator[tuple[int, str]]:
    for i in range(len(digitos) - longitud + 1):
        yield i, digitos[i : i + longitud]


def detectar_en_cadena(cadena: CadenaDeDigitos, texto: str) -> list[Hallazgo]:
    """Analiza una tirada de dígitos y devuelve lo que sea sensible.

    El orden importa: se prueba primero lo más específico y largo. Una tarjeta
    de dieciséis cifras contiene subcadenas de once que pasarían por RUC, así
    que reconocerla primero evita tachar media tarjeta con la etiqueta
    equivocada.
    """
    d = cadena.digitos
    contexto = texto[max(0, cadena.inicio - 60) : cadena.inicio]

    # CCI: veinte dígitos exactos.
    if len(d) == 20:
        return [
            Hallazgo(
                PIIKind.CCI, cadena.inicio, cadena.fin, "20 dígitos: código de cuenta interbancario"
            )
        ]

    # Tarjeta: la validación de Luhn manda sobre cualquier otra interpretación.
    for longitud in (19, 18, 17, 16, 15, 14, 13):
        for offset, trozo in _subcadenas(d, longitud):
            if luhn(trozo):
                inicio, fin = cadena.tramo(offset, offset + longitud)
                return [
                    Hallazgo(
                        PIIKind.NUMERO_TARJETA, inicio, fin, f"{longitud} dígitos válidos por Luhn"
                    )
                ]

    # RUC: once dígitos con prefijo de contribuyente.
    if len(d) == 11 and d.startswith(PREFIJOS_RUC):
        return [Hallazgo(PIIKind.RUC, cadena.inicio, cadena.fin, f"11 dígitos con prefijo {d[:2]}")]

    # DNI: ocho dígitos.
    if len(d) == 8:
        pista = "mencionado tras 'DNI'" if CONTEXTO_DNI.search(contexto) else "8 dígitos"
        return [Hallazgo(PIIKind.DNI, cadena.inicio, cadena.fin, pista)]

    # Teléfono móvil peruano: nueve dígitos empezando por 9.
    if len(d) == 9 and d.startswith("9"):
        return [
            Hallazgo(PIIKind.TELEFONO, cadena.inicio, cadena.fin, "9 dígitos que empiezan por 9")
        ]

    # Una tirada larga sin forma reconocible se tacha igual.
    #
    # Es una decisión conservadora y consciente: ante un número largo que el
    # cliente dictó y no encaja en ningún patrón, es preferible tacharlo que
    # arriesgarse a que fuera una cuenta. El motivo queda registrado para poder
    # revisar si genera ruido.
    if len(d) >= 12:
        return [
            Hallazgo(
                PIIKind.NUMERO_CUENTA,
                cadena.inicio,
                cadena.fin,
                f"{len(d)} dígitos sin patrón conocido",
            )
        ]

    return []


def detectar_cvv(texto: str, cadenas: list[CadenaDeDigitos]) -> list[Hallazgo]:
    """Códigos de seguridad, que sólo son reconocibles por su contexto.

    Tres dígitos sueltos no son nada; tres dígitos después de "el código de
    seguridad es" son lo que ninguna grabación de un banco puede contener.
    """
    hallazgos: list[Hallazgo] = []
    for m in CONTEXTO_CVV.finditer(texto):
        # Se buscan dígitos en la ventana posterior a la frase que los anuncia.
        ventana = texto[m.end() : m.end() + 70]
        from .numeros import extraer_cadenas

        for cadena in extraer_cadenas(ventana, minimo=3):
            if 3 <= len(cadena.digitos) <= 4:
                hallazgos.append(
                    Hallazgo(
                        PIIKind.CVV,
                        m.end() + cadena.inicio,
                        m.end() + cadena.fin,
                        "dígitos anunciados como código de seguridad",
                    )
                )
                break
    # Las cadenas ya analizadas no se vuelven a mirar aquí.
    del cadenas
    return hallazgos
