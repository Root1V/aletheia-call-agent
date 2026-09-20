"""Qué dijo el cliente que importa para clasificar bajo la Ley 31763.

Deterministas y sobre los turnos del CLIENTE, nunca sobre los del ejecutivo.
Eso último no es una restricción heredada de la emoción: es lo que hace útil al
clasificador. Si las señales salieran de lo que dice el ejecutivo —"vamos a
registrar un reclamo formal"—, el copiloto no haría más que repetirle lo que
acaba de decidir, y sería ciego justo al caso que existe para evitar: que el
ejecutivo NO registre un reclamo que correspondía.

Los patrones salen de transcripciones reales del perímetro, no de una lista
inventada: "ya caigo", "disculpe la molestia", "me han robado", "yo nunca he
comprado ahí".
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from enum import StrEnum


class Marca(StrEnum):
    """Familias de señal, cada una con una consecuencia legal distinta."""

    AFECTACION = "afectacion"
    """Presunta afectación de un interés legítimo. Es la definición de reclamo."""

    RETRACTACION = "retractacion"
    """El cliente reconoce el consumo o retira la queja. Cierra sin caso."""

    ESCALAMIENTO = "escalamiento"
    """SBS, Indecopi, Libro de Reclamaciones, abogado. Reclamo sin discusión."""

    PETICION_SIMPLE = "peticion_simple"
    """Gestión sin afectación: copia, constancia, estado de un trámite."""


# Los patrones conservan las negaciones a propósito.
#
# El normalizador de los guardarraíles del copiloto elimina palabras vacías, y
# "no" está entre ellas. Aplicarlo aquí convertiría "no reconozco este cargo" en
# "reconozco cargo", que es lo contrario. Por eso este módulo normaliza sólo
# tildes, mayúsculas y puntuación.
_PATRONES: tuple[tuple[Marca, str, str], ...] = (
    (Marca.AFECTACION, r"\bno\s+(lo\s+)?reconozco\b", "no reconoce el consumo"),
    (Marca.AFECTACION, r"\bno\s+reconoc\w+\b", "no reconoce el consumo"),
    (Marca.AFECTACION, r"\bcargo\s+que\s+no\b", "cargo que no reconoce"),
    (Marca.AFECTACION, r"\byo\s+no\s+(hice|compre|pedi|autorice|solicite)\b", "niega la operación"),
    (
        Marca.AFECTACION,
        r"\bnunca\s+he\s+(comprado|usado|pedido)\b",
        "niega ser cliente del comercio",
    ),
    (Marca.AFECTACION, r"\bme\s+(han\s+)?rob\w+\b", "denuncia robo"),
    (Marca.AFECTACION, r"\bme\s+(cobraron|descontaron|debitaron)\b", "cobro no esperado"),
    (Marca.AFECTACION, r"\bcobro\s+(indebido|duplicado|doble)\b", "cobro indebido"),
    (Marca.AFECTACION, r"\bme\s+cobraron\s+(dos|2)\s+veces\b", "cobro duplicado"),
    (Marca.AFECTACION, r"\bsin\s+(avisar|mi\s+autorizacion|autorizacion)\b", "sin autorización"),
    (
        Marca.AFECTACION,
        r"\bno\s+me\s+(informaron|avisaron|dijeron)\b",
        "falta de información previa",
    ),
    (
        Marca.AFECTACION,
        r"\bes\s+(inaceptable|un\s+abuso|injusto)\b",
        "califica la situación de indebida",
    ),
    (
        Marca.AFECTACION,
        r"\bquiero\s+que\s+me\s+(devuelvan|reintegren|extornen)\b",
        "exige devolución",
    ),
    (Marca.AFECTACION, r"\bfraude\b", "menciona fraude"),
    (Marca.RETRACTACION, r"\bya\s+(caigo|recuerdo|me\s+acorde)\b", "recuerda el consumo"),
    (Marca.RETRACTACION, r"\bdisculpe?\s+(la\s+)?molestia\b", "retira la queja"),
    (Marca.RETRACTACION, r"\btiene\s+razon\b", "acepta la explicación"),
    (Marca.RETRACTACION, r"\bera\s+(mio|mia|mi\s+compra)\b", "reconoce el consumo como propio"),
    (Marca.RETRACTACION, r"\bah,?\s*(si|ya)\b.{0,30}\b(fui|compre|era)\b", "recuerda el consumo"),
    (Marca.RETRACTACION, r"\bno,?\s+(eso\s+)?era\s+todo\b", "cierra sin pedir nada"),
    (Marca.RETRACTACION, r"\bentonces\s+esta\s+bien\b", "se da por satisfecho"),
    (Marca.ESCALAMIENTO, r"\bsbs\b", "menciona la SBS"),
    (Marca.ESCALAMIENTO, r"\bindecopi\b", "menciona Indecopi"),
    (Marca.ESCALAMIENTO, r"\blibro\s+de\s+reclamaciones\b", "pide el Libro de Reclamaciones"),
    (Marca.ESCALAMIENTO, r"\babogado\b", "menciona un abogado"),
    (
        Marca.ESCALAMIENTO,
        r"\b(poner|presentar|registrar)\s+(un\s+)?reclamo\b",
        "pide registrar un reclamo",
    ),
    (
        Marca.ESCALAMIENTO,
        r"\bquiero\s+que\s+quede\s+(registrado|constancia)\b",
        "pide constancia formal",
    ),
    (Marca.ESCALAMIENTO, r"\bvoy\s+a\s+(denunciar|quejarme)\b", "anuncia denuncia"),
    (Marca.PETICION_SIMPLE, r"\b(copia|constancia)\s+(de|del)\b", "solicita un documento"),
    (
        Marca.PETICION_SIMPLE,
        r"\bestado\s+de\s+mi\s+(tramite|solicitud|reclamo)\b",
        "consulta un trámite",
    ),
    (Marca.PETICION_SIMPLE, r"\bcomo\s+(va|quedo)\s+(mi|lo\s+de)\b", "consulta un trámite"),
    (
        Marca.PETICION_SIMPLE,
        r"\bactualizar\s+mis?\s+(datos|direccion|telefono|correo)\b",
        "actualización de datos",
    ),
    (Marca.PETICION_SIMPLE, r"\bquiero\s+(consultar|saber|preguntar)\b", "consulta"),
    (Marca.PETICION_SIMPLE, r"\bme\s+puede\s+(enviar|mandar)\b", "solicita un envío"),
)

_COMPILADOS = tuple((m, re.compile(p), d) for m, p, d in _PATRONES)


def normalizar(texto: str) -> str:
    """Sin tildes, en minúsculas, sin puntuación. **Con las negaciones intactas.**"""
    base = unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^\w\s]", " ", base)


@dataclass(slots=True, frozen=True)
class Hallazgo:
    """Una señal encontrada, con dónde estaba."""

    marca: Marca
    turn_id: str
    orden: int
    """Posición del turno en la conversación. Es lo que permite saber si una
    retractación llegó DESPUÉS de la queja o antes, que cambia su significado."""
    descripcion: str
    cita: str


@dataclass(slots=True)
class Senales:
    """Todo lo encontrado en los turnos del cliente."""

    hallazgos: list[Hallazgo] = field(default_factory=list)

    def de(self, marca: Marca) -> list[Hallazgo]:
        return [h for h in self.hallazgos if h.marca is marca]

    def ultimo(self, marca: Marca) -> Hallazgo | None:
        encontrados = self.de(marca)
        return max(encontrados, key=lambda h: h.orden) if encontrados else None

    def tiene(self, marca: Marca) -> bool:
        return any(h.marca is marca for h in self.hallazgos)


def extraer(turnos: list[tuple[str, str]]) -> Senales:
    """Señales de los turnos del cliente, en orden.

    `turnos` son pares (turn_id, texto) YA filtrados al hablante cliente. Que el
    filtrado ocurra fuera es deliberado: quien llama tiene el evento con su
    `speaker` tipado, y recibir aquí la conversación entera invitaría a colar los
    turnos del ejecutivo sin que nada lo impidiera.
    """
    senales = Senales()
    for orden, (turn_id, texto) in enumerate(turnos):
        plano = normalizar(texto)
        for marca, patron, descripcion in _COMPILADOS:
            encontrado = patron.search(plano)
            if encontrado is None:
                continue
            if any(
                h.turn_id == turn_id and h.descripcion == descripcion for h in senales.hallazgos
            ):
                continue
            senales.hallazgos.append(
                Hallazgo(
                    marca=marca,
                    turn_id=turn_id,
                    orden=orden,
                    descripcion=descripcion,
                    cita=_recortar(texto, encontrado.start(), encontrado.end()),
                )
            )
    return senales


# Cuánto contexto se conserva alrededor de la coincidencia.
#
# La cita se le muestra al ejecutivo para que contraste la clasificación. Una
# cita de tres palabras no se puede contrastar; el turno entero tampoco se lee
# de un vistazo mientras se habla con alguien.
_MARGEN = 45


def _recortar(texto: str, inicio: int, fin: int) -> str:
    desde = max(0, inicio - _MARGEN)
    hasta = min(len(texto), fin + _MARGEN)
    fragmento = texto[desde:hasta].strip()
    return ("…" if desde > 0 else "") + fragmento + ("…" if hasta < len(texto) else "")
