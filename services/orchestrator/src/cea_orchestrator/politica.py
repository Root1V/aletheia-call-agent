"""Cuándo pedirle una sugerencia al modelo.

El componente más fácil de subestimar del copiloto. Un sistema que sugiere ante
cada turno del cliente es peor que uno que no sugiere nada: el ejecutivo recibe
una tarjeta nueva mientras está leyendo la anterior, deja de mirarlas, y el
producto queda instalado pero sin usar. La bibliografía del sector lo señala
como la causa número uno de abandono de estas herramientas, por delante de la
calidad del modelo.

Todas las decisiones de aquí son deterministas y baratas. Ninguna necesita un
modelo, y meter uno añadiría al camino crítico la latencia que el producto
gasta en lo que sí importa.
"""

from __future__ import annotations

import re
import time
import unicodedata
from dataclasses import dataclass, field

from cea_contracts import Speaker

# Longitud mínima del turno, en palabras.
#
# "Sí", "ajá", "correcto" y "ya" son la mitad de los turnos de una llamada y no
# piden nada. Generar sobre ellos gasta el modelo y llena la pantalla de
# tarjetas que el ejecutivo no pidió.
MINIMO_PALABRAS = 5

# Enfriamiento entre sugerencias.
#
# No es para proteger a la plataforma: es para proteger la atención del
# ejecutivo. Seis segundos es aproximadamente lo que se tarda en leer una frase
# de cuarenta palabras y decidir si usarla.
ENFRIAMIENTO_S = 6.0


def _sin_tildes(palabra: str) -> str:
    return unicodedata.normalize("NFKD", palabra.lower()).encode("ascii", "ignore").decode("ascii")


def _vocabulario(texto: str) -> frozenset[str]:
    """Normaliza las listas igual que el texto que se compara contra ellas.

    Sin esto la trampa es silenciosa: el turno llega normalizado a ASCII
    —"señorita" se convierte en "senorita"— y una lista escrita con eñe no casa
    nunca. La palabra parece estar y no está, y sólo se descubre probando.
    """
    return frozenset(_sin_tildes(p) for p in texto.split())


# Vocabulario de cierre y cortesía.
#
# Un turno que sólo agradece o asiente no pide nada, y generar sobre él no es
# neutro: es donde el modelo confabula. Medido sobre una llamada real, ante "De
# acuerdo, gracias por la ayuda" el modelo escribió tres veces de tres:
#
#     «Entendido, le informo que se ha generado el folio correspondiente
#      para atender su reclamo»
#
# No existe tal folio —el registro de casos es RF-16 y está en el backlog— y esa
# frase se la habría dicho el ejecutivo al cliente. Los guardarraíles la
# bloquearon las tres veces, pero el arreglo correcto es no pedirla: un modelo
# sin material contesta igual, y lo que inventa cuando no tiene nada que decir es
# justo lo que más daño hace.
#
# Se reconoce por VOCABULARIO y no contando lo que sobra. Contar sobrantes
# silenciaba "está bien, ¿y el dinero me lo devuelven?" —dos palabras con
# contenido— que es la pregunta más importante de una disputa. Un turno es de
# cierre sólo si TODO lo que dice está en esta lista.
_CIERRE: frozenset[str] = _vocabulario(
    """
    gracias muchas mil amable amabilidad ayuda atencion tiempo paciencia
    acuerdo esta bien perfecto listo correcto entendido claro vale okey
    eso era todo nada mas menos hasta luego pronto chau adios
    buenos buenas dias tardes noches señor señora señorita
    favor disculpe disculpa perdon molestia pena sip ajam
    """
)

# Palabras que no cuentan para decidir: gramática y muletillas.
#
# Van aparte del vocabulario de cierre porque significan cosas distintas. Que un
# turno lleve "entonces" no lo hace un cierre; que no lleve nada MÁS que
# gramática y cortesía, sí. Sin esta lista el criterio no marcaba ni un turno:
# "de acuerdo, gracias por la ayuda" trae "de" y "la", que no son cierre pero
# tampoco contenido, y bastaban para que el turno pareciera decir algo.
_VACIAS: frozenset[str] = _vocabulario(
    """
    el la los las un una unos unas lo al del
    de en por para con sin sobre entre desde hasta
    que quien cual cuando donde como
    yo tu el ella usted ustedes nosotros me te se nos le les mi su sus tus
    es son era eran fue ha han he has hay esta estan estoy estas
    muy mas menos tan ya aun aunque pero sino porque pues entonces osea
    este esta esto ese esa eso aquel
    si no
    """
)


@dataclass(slots=True)
class Politica:
    """Estado de decisión de una llamada."""

    ultima_emision: float = 0.0
    turnos_del_cliente: int = 0
    _reloj: object = field(default=time.monotonic, repr=False)

    def evaluar(self, speaker: Speaker, texto: str) -> str | None:
        """Devuelve el motivo por el que NO se sugiere, o None si procede.

        Se devuelve el motivo en lugar de un booleano porque acaba en el log y
        en las evaluaciones: "no sugirió" sin causa es indistinguible de un
        fallo, y la primera pregunta al ver una llamada sin sugerencias es
        siempre por qué.
        """
        if speaker is not Speaker.CUSTOMER:
            # El ejecutivo no necesita que se le sugiera una respuesta a sí
            # mismo. Además, disparar sobre su turno significaría medir su
            # intervención, que es justo lo que este producto no hace.
            return "turno del ejecutivo"

        self.turnos_del_cliente += 1

        if len(texto.split()) < MINIMO_PALABRAS:
            return f"turno demasiado corto ({len(texto.split())} palabras)"

        if _es_cierre(texto):
            return "sólo cortesía o cierre"

        transcurrido = self._ahora() - self.ultima_emision
        if self.ultima_emision and transcurrido < ENFRIAMIENTO_S:
            return f"enfriamiento ({transcurrido:.1f}s de {ENFRIAMIENTO_S:.0f}s)"

        return None

    def anotar_emision(self) -> None:
        self.ultima_emision = self._ahora()

    def _ahora(self) -> float:
        return self._reloj()  # type: ignore[operator]


def _es_cierre(texto: str) -> bool:
    """¿El turno sólo agradece, asiente o se despide?

    Las tildes se normalizan a ambos lados: el reconocedor devuelve "sí" y "si"
    indistintamente según la entonación, y comparar formas distintas deja pasar
    la mitad de los asentimientos.
    """
    plano = _sin_tildes(texto)
    palabras = [p for p in re.sub(r"[^\w\s]", " ", plano).split() if len(p) > 1]
    if not palabras:
        return True
    return all(p in _CIERRE or p in _VACIAS for p in palabras)
