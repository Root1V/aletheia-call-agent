"""Verificación de las cifras que emite el modelo.

Es el control que impide un incidente regulatorio, y no lo es el prompt. Por
bien redactado que esté, un modelo generativo puede producir una comisión
plausible que no existe, y lo hará con la misma fluidez que una correcta.

No es una precaución teórica: en la primera generación real contra la
plataforma, el modelo de 20B escribió "una tarifa legítima por los 6 viajes"
cuando eran 189 soles de UN cargo y seis compras previas sin relación con el
importe.

La regla es simple y deliberadamente estricta: toda cantidad que aparezca en la
sugerencia tiene que estar o en el contexto que se le dio al modelo, o en la
tabla de cifras citables. Una cifra que el modelo compuso por su cuenta —aunque
sea la suma correcta de dos que sí le dimos— no pasa.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Cantidades en el texto generado.
#
# Se capturan importes, porcentajes y números sueltos por separado porque la
# comparación es distinta: 45 y 45.00 son la misma comisión, pero 45 y 45%
# no son lo mismo en absoluto.
#
# El número acepta DOS formas y en este orden: con separador de miles
# ("1,450.00") y sin él ("1450.00"). La versión anterior sólo contemplaba la
# primera, y el fallo era grave en las dos direcciones: de "S/ 1450.00" extraía
# 145 —bloqueaba una cifra correcta— y del contexto "PEN 1450.00" no extraía
# nada, de modo que una justificación que dijera "S/ 145" habría pasado la
# verificación con el importe real en 1450. Aprobar una cifra equivocada es
# justamente lo que este módulo existe para impedir.
#
# Aparece con importes de cuatro cifras, que en banca peruana son cotidianos:
# el escenario de fraude son S/ 1,450.00, y nuestro propio generador de contexto
# los formatea sin separador.
_CANTIDAD = r"\d{1,3}(?:[,\s]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?"

_IMPORTE = re.compile(rf"S/\s*({_CANTIDAD})")
_PORCENTAJE = re.compile(r"([\d]+(?:[.,]\d+)?)\s*(?:%|por\s+ciento)")
_NUMERO = re.compile(rf"(?<![\d.,])({_CANTIDAD})(?![\d.,%])")

# Números que no son datos.
#
# Sin esta lista, "una o dos opciones" dispararía la verificación. Son
# cantidades del lenguaje, no cifras citables.
_TRIVIALES = {0.0, 1.0, 2.0, 3.0}

# Tramos del texto que contienen números pero no cantidades.
#
# Una hora y una fecha llevan cifras que no son importes ni plazos, y tratarlas
# como tales bloquea sugerencias CORRECTAS: "el cargo del 10/09 a las 15:37"
# disparaba la verificación por el "37" de los minutos. Un control que se come
# respuestas buenas acaba desactivado, así que estos tramos se excluyen antes
# de extraer nada.
#
# La hora se reconoce SÓLO por los dos puntos. Aceptar el punto como separador
# —"15.37"— hace que el patrón capture también los importes: "S/ 31.65" y
# "S/ 52.00" encajan en \d{1,2}[.]\d{2} y quedarían exentos de verificación,
# que es exactamente lo contrario de lo que hace falta.
_NO_ES_CANTIDAD = re.compile(
    r"""
    \b\d{1,2}:\d{2}(?::\d{2})?\b              # hora: 15:37 — SÓLO con dos puntos
  | \b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b          # fecha: 10/09, 10/09/2026
  | \b\d{1,2}\s+de\s+\w+                      # fecha en palabras: 10 de setiembre
  | \b(?:19|20)\d{2}\b                          # año suelto
  | \*{2,}\d+                                   # dato enmascarado: ***4521
    """,
    re.X | re.IGNORECASE,
)


@dataclass(slots=True, frozen=True)
class Cantidad:
    valor: float
    unidad: str
    literal: str

    def coincide(self, otro: Cantidad) -> bool:
        """¿Son la misma cifra?

        La única unidad que separa de verdad es el PORCENTAJE: 45 y 45% no son
        lo mismo en absoluto, y confundirlos en un tarifario es un incidente.
        Un importe y un número suelto del mismo valor sí son la misma cifra
        dicha de dos maneras, y tratarlos como distintos bloqueaba
        justificaciones correctas: nuestro propio resumen de la llamada escribe
        "PEN 1450.00" y el modelo responde "S/ 1450.00".
        """
        if (self.unidad == "porcentaje") != (otro.unidad == "porcentaje"):
            return False
        # Tolerancia de un céntimo: "S/ 45" y "S/ 45.00" son la misma comisión.
        return abs(self.valor - otro.valor) < 0.005


@dataclass(slots=True, frozen=True)
class Verificacion:
    respaldadas: tuple[Cantidad, ...]
    sin_respaldo: tuple[Cantidad, ...]

    @property
    def aprobada(self) -> bool:
        return not self.sin_respaldo

    @property
    def motivo(self) -> str:
        if self.aprobada:
            return ""
        literales = ", ".join(sorted({c.literal for c in self.sin_respaldo}))
        return f"cifras sin respaldo en el contexto ni en el tarifario: {literales}"


def _a_float(texto: str) -> float | None:
    limpio = texto.replace(" ", "").replace(",", "")
    try:
        return float(limpio)
    except ValueError:
        return None


def extraer_cantidades(texto: str) -> list[Cantidad]:
    """Saca del texto toda cantidad comparable.

    Los tramos que son horas, fechas o datos enmascarados se tachan antes: sus
    dígitos no son cantidades y tratarlos como tales bloquea sugerencias
    correctas.
    """
    # Se sustituye por espacios en lugar de recortar, para que las posiciones
    # de los demás patrones sigan siendo válidas.
    texto = _NO_ES_CANTIDAD.sub(lambda m: " " * len(m.group()), texto)

    encontradas: list[Cantidad] = []
    cubierto: list[tuple[int, int]] = []

    for patron, unidad in ((_IMPORTE, "pen"), (_PORCENTAJE, "porcentaje")):
        for m in patron.finditer(texto):
            if (v := _a_float(m.group(1))) is not None:
                encontradas.append(Cantidad(v, unidad, m.group(0).strip()))
                cubierto.append(m.span())

    for m in _NUMERO.finditer(texto):
        # Un número ya contado como importe o porcentaje no se cuenta otra vez.
        if any(ini <= m.start() < fin for ini, fin in cubierto):
            continue
        if (v := _a_float(m.group(1))) is not None and v not in _TRIVIALES:
            encontradas.append(Cantidad(v, "numero", m.group(0).strip()))

    return encontradas


def verificar(sugerencia: str, contexto: str, hechos: list[tuple[float, str]]) -> Verificacion:
    """Comprueba que toda cifra de la sugerencia tenga respaldo.

    `contexto` es todo lo que se le pasó al modelo —los pasajes recuperados y
    los datos de la llamada— y `hechos` son las cifras citables del tarifario
    como pares (valor, unidad).

    Importes y números sueltos se comparan sólo por valor: el modelo puede
    escribir "45 soles" donde el documento decía "S/ 45.00", y al revés. Lo que
    NO se cruza es el porcentaje, porque 45 y 45% no son la misma cifra y
    confundirlos en un tarifario es un incidente.
    """
    del_contexto = extraer_cantidades(contexto)
    de_hechos = [Cantidad(v, u, f"{v}") for v, u in hechos]
    disponibles = del_contexto + de_hechos

    respaldadas: list[Cantidad] = []
    sin_respaldo: list[Cantidad] = []

    for cantidad in extraer_cantidades(sugerencia):
        ok = any(cantidad.coincide(d) for d in disponibles)
        (respaldadas if ok else sin_respaldo).append(cantidad)

    return Verificacion(tuple(respaldadas), tuple(sin_respaldo))
