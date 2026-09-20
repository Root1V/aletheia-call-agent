"""El modelo redacta el porqué. No decide el qué.

La clasificación ya está tomada por `ley31763.clasificar` cuando esto se
ejecuta. Aquí el modelo sólo convierte la regla aplicada y la evidencia en una
frase que el ejecutivo pueda leer, contrastar y pegar en el caso.

El reparto no es una preferencia de estilo. Una clasificación que sale de un
modelo no se puede explicar ante la SBS —"el verificador le dio 0.83" no es una
respuesta a por qué se privó a un usuario del plazo legal— mientras que una
regla sí. Y la redacción, que es lo que un modelo hace bien, no tiene
consecuencia regulatoria mientras no contradiga el veredicto. Que no lo
contradiga se comprueba después, y con reglas.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from cea_contracts import CaseType
from cea_copilot import verificar
from cea_llm import Mensaje, ProveedorLLM

from .ley31763 import Desenlace, Dictamen

log = logging.getLogger("cea.reclamos")

MAX_TOKENS = 130

SISTEMA = """\
Eres el copiloto de un ejecutivo de atención telefónica de un banco peruano.

Se te entrega una clasificación YA DECIDIDA por el procedimiento del banco bajo \
la Ley 31763, con la regla aplicada y la evidencia de la conversación. Tu única \
tarea es redactar la justificación que acompañará al caso.

Reglas:
- Máximo 45 palabras, una o dos frases.
- NO cambies la clasificación ni la discutas. Ya está decidida.
- Explica por qué, apoyándote en lo que el cliente dijo.
- No inventes hechos, montos, fechas ni plazos que no estén en lo que se te da.
- Escribe para el expediente, en tercera persona: "El cliente manifiesta que…".
- No te dirijas al cliente ni al ejecutivo.\
"""

_ETIQUETA = {
    CaseType.RECLAMO: "RECLAMO",
    CaseType.REQUERIMIENTO: "REQUERIMIENTO",
}


@dataclass(slots=True, frozen=True)
class Justificacion:
    texto: str
    generada: bool
    """False cuando se usó el texto de la regla porque el modelo falló o se
    desvió. La distinción importa en auditoría: no es lo mismo una justificación
    escrita por el modelo que el enunciado de la regla."""

    motivo_del_descarte: str | None = None
    """Por qué se descartó el texto del modelo. Va al log de auditoría: una
    justificación seca sin explicación parece un fallo del sistema."""


def _veredicto(d: Dictamen) -> str:
    if d.desenlace is Desenlace.RESUELTO_EN_LLAMADA:
        return "RESUELTO EN LA LLAMADA, sin abrir caso"
    if d.tipo is not None:
        return f"{_ETIQUETA[d.tipo]}, se abre caso"
    return "SIN MATERIA, no se abre caso"


def _prompt(d: Dictamen, contexto: str) -> list[Mensaje]:
    evidencia = "\n".join(f"- {e}" for e in d.evidencia) or "- (sin citas)"
    return [
        Mensaje("system", SISTEMA),
        Mensaje(
            "user",
            f"CLASIFICACIÓN DECIDIDA: {_veredicto(d)}\n"
            f"REGLA APLICADA: {d.regla}\n\n"
            f"EVIDENCIA DE LA CONVERSACIÓN:\n{evidencia}\n\n"
            f"DATOS DE LA LLAMADA:\n{contexto or '(sin datos adicionales)'}\n\n"
            f"Redacta la justificación para el expediente.",
        ),
    ]


# Palabras con las que una justificación estaría clasificando por su cuenta.
#
# El modelo no tiene autoridad para decir que algo "no corresponde a un reclamo":
# eso ya se decidió. Si lo escribe, se descarta su texto y se conserva el de la
# regla — el expediente prefiere una frase sosa a una que contradice el veredicto
# que encabeza.
_CONTRADICCIONES = (
    (CaseType.RECLAMO, re.compile(r"\b(es|constituye|corresponde a)\s+un\s+requerimiento\b", re.I)),
    (
        CaseType.RECLAMO,
        re.compile(r"\bno\s+(constituye|corresponde|procede)\b.{0,20}reclamo", re.I),
    ),
    (
        CaseType.REQUERIMIENTO,
        re.compile(r"\b(es|constituye|corresponde a)\s+un\s+reclamo\b", re.I),
    ),
)


def contradice(texto: str, tipo: CaseType | None) -> bool:
    """¿La justificación desdice la clasificación que encabeza?"""
    if tipo is None:
        return False
    return any(patron.search(texto) for esperado, patron in _CONTRADICCIONES if esperado is tipo)


async def redactar(
    proveedor: ProveedorLLM,
    dictamen: Dictamen,
    *,
    datos_de_la_llamada: str = "",
    hechos: list[tuple[float, str]] | None = None,
) -> Justificacion:
    """Justificación del dictamen, o el texto de la regla si el modelo no sirve.

    Nunca falla hacia arriba. Una llamada terminada no puede quedarse sin
    clasificar porque el modelo no respondió: la regla ya decidió y su enunciado
    es una justificación válida, sólo que más seca.
    """
    try:
        respuesta = await proveedor.completar(
            _prompt(dictamen, datos_de_la_llamada),
            max_tokens=MAX_TOKENS,
            temperatura=0.2,
            esfuerzo="ninguno",
        )
        texto = respuesta.texto.strip().strip('"')
    except Exception:  # noqa: BLE001
        log.warning("El modelo no redactó la justificación; se usa la regla", exc_info=True)
        return Justificacion(texto=dictamen.regla, generada=False)

    if not texto:
        return Justificacion(dictamen.regla, generada=False, motivo_del_descarte="vacía")

    if contradice(texto, dictamen.tipo):
        log.warning("La justificación contradecía el veredicto; se descarta: %r", texto)
        return Justificacion(
            dictamen.regla, generada=False, motivo_del_descarte="contradecía la clasificación"
        )

    # Las cifras se verifican igual que en una sugerencia, y por una razón más
    # fuerte: esto va al expediente de un caso regulado. Una justificación que
    # dice "un consumo de S/ 1.450,00" cuando fueron 1.045 no la corrige nadie
    # después; queda en el registro que se le entrega al usuario y a la SBS.
    material = "\n".join((datos_de_la_llamada, *dictamen.evidencia))
    cifras = verificar(texto, material, hechos or [])
    if not cifras.aprobada:
        log.warning("Cifra sin respaldo en la justificación; se descarta: %s", cifras.motivo)
        return Justificacion(dictamen.regla, generada=False, motivo_del_descarte=cifras.motivo)

    return Justificacion(texto=texto, generada=True)
