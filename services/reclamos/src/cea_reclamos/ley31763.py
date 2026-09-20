"""La clasificación reclamo / requerimiento, y si procede abrir caso.

Reglas explícitas, no un modelo. La decisión tiene consecuencia legal —clasificar
un reclamo como requerimiento priva al usuario del plazo de quince días hábiles y
de la vía de escalamiento a la SBS, y es un incumplimiento— así que tiene que
poder explicarse ante un auditor con la regla que se aplicó, no con una
puntuación. El modelo entra después, y sólo para REDACTAR la justificación de lo
que ya se decidió aquí.

La regla que gobierna todo lo demás está en el procedimiento del banco y es
explícita: **ante la duda se registra como reclamo.** De ahí que los empates, los
casos vacíos y los ambiguos caigan todos del mismo lado, y que la confianza se
mantenga por debajo de 1.0 incluso cuando las señales son claras.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from cea_contracts import CaseType

from .senales import Marca, Senales


class Desenlace(StrEnum):
    """Qué hacer al cerrar la llamada."""

    ABRIR_CASO = "abrir_caso"
    RESUELTO_EN_LLAMADA = "resuelto_en_llamada"
    SIN_MATERIA = "sin_materia"
    """Nada en la conversación pide una gestión. No se propone nada: inventar un
    caso donde no lo hay satura la operación y dispara plazos sin motivo."""


@dataclass(slots=True, frozen=True)
class Dictamen:
    """Lo que el copiloto propone, con de dónde sale."""

    desenlace: Desenlace
    tipo: CaseType | None
    confianza: float
    regla: str
    """La regla aplicada, en una frase. Es lo que se audita."""
    evidencia: tuple[str, ...]
    turnos_de_evidencia: tuple[str, ...]

    @property
    def abre_caso(self) -> bool:
        return self.desenlace is Desenlace.ABRIR_CASO


# Confianzas por regla.
#
# Ninguna llega a 1.0 a propósito: una predicción que se declara segura y falla
# cuesta más credibilidad que una prudente, y aquí además el ejecutivo tiene que
# CONFIRMAR. Una confianza de 1.0 invita a confirmar sin leer, que es exactamente
# el automatismo que este control existe para evitar.
CONFIANZA_ESCALAMIENTO = 0.95
CONFIANZA_AFECTACION = 0.85
CONFIANZA_RETRACTACION = 0.75
CONFIANZA_PETICION = 0.80
CONFIANZA_DUDA = 0.50


def clasificar(senales: Senales) -> Dictamen:
    """Aplica la Ley 31763 sobre lo que el cliente dijo.

    El orden de las reglas es el orden de prevalencia legal, y no es negociable:
    una petición de registrar un reclamo gana a cualquier otra cosa, y una
    retractación sólo cuenta si llegó DESPUÉS de la queja que retira.
    """
    escalamiento = senales.ultimo(Marca.ESCALAMIENTO)
    afectacion = senales.ultimo(Marca.AFECTACION)
    retractacion = senales.ultimo(Marca.RETRACTACION)
    peticion = senales.ultimo(Marca.PETICION_SIMPLE)

    # 1 · El cliente pide expresamente dejar constancia, o nombra a la SBS, a
    #     Indecopi o al Libro de Reclamaciones. No hay nada que interpretar: el
    #     usuario está ejerciendo su derecho y negárselo es el incumplimiento.
    if escalamiento is not None:
        return _dictamen(
            Desenlace.ABRIR_CASO,
            CaseType.RECLAMO,
            CONFIANZA_ESCALAMIENTO,
            "El cliente pidió dejar constancia formal o invocó la vía de escalamiento.",
            senales,
            (Marca.ESCALAMIENTO, Marca.AFECTACION),
        )

    # 2 · Hubo afectación y el cliente NO se retractó después.
    if afectacion is not None and not _retractado(afectacion, retractacion):
        return _dictamen(
            Desenlace.ABRIR_CASO,
            CaseType.RECLAMO,
            CONFIANZA_AFECTACION,
            "El cliente expresó una presunta afectación y no la retiró durante la llamada.",
            senales,
            (Marca.AFECTACION,),
        )

    # 3 · Hubo afectación pero el cliente la retiró: se resolvió explicando.
    #
    #     Es el 61% de las disputas —cargos que el cliente no reconoce y resultan
    #     ser suyos— y abrir un caso por cada una satura la operación y dispara
    #     los plazos de la Ley 31763 sin motivo. Sigue siendo una PROPUESTA: el
    #     ejecutivo la confirma, y si el cliente quiere constancia se abre igual.
    if afectacion is not None and retractacion is not None:
        return _dictamen(
            Desenlace.RESUELTO_EN_LLAMADA,
            None,
            CONFIANZA_RETRACTACION,
            "El cliente reconoció el consumo o retiró la queja tras la explicación.",
            senales,
            (Marca.RETRACTACION, Marca.AFECTACION),
        )

    # 4 · Sólo una gestión, sin afectación de por medio.
    if peticion is not None:
        return _dictamen(
            Desenlace.ABRIR_CASO,
            CaseType.REQUERIMIENTO,
            CONFIANZA_PETICION,
            "El cliente solicitó una gestión sin alegar afectación de un interés legítimo.",
            senales,
            (Marca.PETICION_SIMPLE,),
        )

    # 5 · Nada. No se propone un caso que nadie pidió.
    return Dictamen(
        desenlace=Desenlace.SIN_MATERIA,
        tipo=None,
        confianza=CONFIANZA_DUDA,
        regla="No se encontró en la conversación ni afectación ni solicitud de gestión.",
        evidencia=(),
        turnos_de_evidencia=(),
    )


def _retractado(afectacion, retractacion) -> bool:
    """¿La retractación llegó después de la queja?

    El orden es lo que le da sentido. "Ya caigo, era mío" dicho ANTES de
    descubrir un segundo cargo no retira nada: el cliente reconoció una cosa y
    sigue disputando otra. Comparar sólo la presencia de ambas marcas trataría
    esas dos conversaciones como si fueran la misma.
    """
    return retractacion is not None and retractacion.orden >= afectacion.orden


def _dictamen(
    desenlace: Desenlace,
    tipo: CaseType | None,
    confianza: float,
    regla: str,
    senales: Senales,
    marcas: tuple[Marca, ...],
) -> Dictamen:
    # El orden de `marcas` es el de importancia para la regla, y se respeta: la
    # primera familia es la que DECIDIÓ. Ordenar todo cronológicamente dejaría la
    # retractación —el motivo de que no se abra caso— sepultada bajo las tres
    # frases de queja que la preceden, y el ejecutivo tiene que poder contrastar
    # el veredicto leyendo la primera línea.
    hallazgos = [h for m in marcas for h in sorted(senales.de(m), key=lambda x: x.orden)]
    return Dictamen(
        desenlace=desenlace,
        tipo=tipo,
        confianza=confianza,
        regla=regla,
        evidencia=tuple(f"{h.descripcion}: «{h.cita}»" for h in hallazgos),
        turnos_de_evidencia=tuple(dict.fromkeys(h.turn_id for h in hallazgos)),
    )
