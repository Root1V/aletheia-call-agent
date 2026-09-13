"""Métricas de reconocimiento.

El WER se calcula sobre texto normalizado: minúsculas, sin tildes y sin
puntuación. Un reconocedor que escribe "crédito" y otro que escribe "credito"
no cometen un error de reconocimiento, y contarlo como tal enmascara los
errores de verdad.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

_NO_PALABRA = re.compile(r"[^\w\s]", re.UNICODE)

# Grafías alternativas aceptadas en español.
#
# Que el modelo escriba "septiembre" donde el guion dice "setiembre" no es un
# error de reconocimiento: ambas formas son correctas y la segunda es la
# habitual en Perú. Contarlas como error infla el WER y, peor, esconde los
# errores reales detrás de ruido ortográfico. La lista se mantiene corta y
# justificada a propósito: cada entrada que se añada sin motivo convierte la
# métrica en una forma de maquillar resultados.
_VARIANTES = {
    "septiembre": "setiembre",
    "setiembre": "setiembre",
    "octubre": "octubre",
    "sicologia": "psicologia",
    "psicologia": "psicologia",
    "sustancia": "substancia",
    "substancia": "substancia",
}


def normalizar(texto: str) -> list[str]:
    sin_tildes = (
        unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode("ascii")
    )
    palabras = _NO_PALABRA.sub(" ", sin_tildes).split()
    return [_VARIANTES.get(p, p) for p in palabras]


@dataclass(slots=True, frozen=True)
class ResultadoWER:
    sustituciones: int
    inserciones: int
    borrados: int
    palabras_referencia: int

    @property
    def errores(self) -> int:
        return self.sustituciones + self.inserciones + self.borrados

    @property
    def wer(self) -> float:
        if self.palabras_referencia == 0:
            return 0.0
        return self.errores / self.palabras_referencia * 100


def calcular_wer(referencia: str, hipotesis: str) -> ResultadoWER:
    """Levenshtein a nivel de palabra con desglose de tipo de error.

    Distinguir sustituciones de inserciones y borrados importa: un modelo que
    alucina palabras de más y otro que se come el final de cada frase pueden
    tener el mismo WER y requerir arreglos opuestos.
    """
    r, h = normalizar(referencia), normalizar(hipotesis)
    n, m = len(r), len(h)

    # d[i][j] = (coste, sustituciones, inserciones, borrados)
    d: list[list[tuple[int, int, int, int]]] = [[(0, 0, 0, 0)] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        d[i][0] = (i, 0, 0, i)
    for j in range(1, m + 1):
        d[0][j] = (j, 0, j, 0)

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if r[i - 1] == h[j - 1]:
                d[i][j] = d[i - 1][j - 1]
                continue
            sus = d[i - 1][j - 1]
            bor = d[i - 1][j]
            ins = d[i][j - 1]
            mejor = min(sus[0], bor[0], ins[0])
            if sus[0] == mejor:
                d[i][j] = (mejor + 1, sus[1] + 1, sus[2], sus[3])
            elif bor[0] == mejor:
                d[i][j] = (mejor + 1, bor[1], bor[2], bor[3] + 1)
            else:
                d[i][j] = (mejor + 1, ins[1], ins[2] + 1, ins[3])

    _, sus, ins, bor = d[n][m]
    return ResultadoWER(sustituciones=sus, inserciones=ins, borrados=bor, palabras_referencia=n)
