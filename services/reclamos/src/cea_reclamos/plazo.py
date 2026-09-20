"""El reloj de los quince días hábiles.

El plazo de la Ley 31763 no es decorativo: si vence sin respuesta, el usuario
puede acudir a la SBS o a Indecopi. El ejecutivo necesita ver, mientras habla,
si tiene delante a alguien cuyo plazo vence mañana — porque esa llamada se
atiende distinto.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from cea_contracts import fmt_fecha, habiles_despues, to_lima

# Días hábiles para responder un reclamo. Ley 31763.
DIAS_DE_PLAZO = 15

# Cuándo el reloj deja de ser informativo y pasa a ser una alerta.
#
# Tres días hábiles es lo que el área de reclamos necesita para investigar con el
# comercio antes de responder. Avisar el último día no sirve de nada.
UMBRAL_ALERTA_DIAS = 3


class EstadoDelPlazo(StrEnum):
    HOLGADO = "holgado"
    POR_VENCER = "por_vencer"
    VENCIDO = "vencido"


@dataclass(slots=True, frozen=True)
class Plazo:
    """El reloj de un caso, ya resuelto para pintarlo."""

    vence_el: datetime
    dias_habiles_restantes: int
    estado: EstadoDelPlazo

    @property
    def etiqueta(self) -> str:
        """Lo que se muestra, en términos que el ejecutivo puede usar al teléfono."""
        if self.estado is EstadoDelPlazo.VENCIDO:
            return f"Plazo VENCIDO el {fmt_fecha(self.vence_el)}"
        if self.dias_habiles_restantes == 0:
            return f"Vence HOY, {fmt_fecha(self.vence_el)}"
        if self.dias_habiles_restantes == 1:
            return f"Vence mañana, {fmt_fecha(self.vence_el)}"
        return f"{self.dias_habiles_restantes} días hábiles ({fmt_fecha(self.vence_el)})"


def vencimiento(presentado: datetime) -> datetime:
    """Cuándo vence el plazo de un reclamo presentado en ese momento.

    Se cuenta **desde el día siguiente** a la presentación, como dice la norma.
    `habiles_despues` ya empieza a contar en el día siguiente, así que sumar
    quince produce el cómputo correcto y no dieciséis.
    """
    return habiles_despues(presentado, DIAS_DE_PLAZO)


def estado(vence_el: datetime, ahora: datetime | None = None) -> Plazo:
    """El reloj de un caso ya abierto."""
    ahora = ahora or datetime.now(UTC)
    restantes = _habiles_entre(ahora, vence_el)

    if ahora > vence_el:
        situacion = EstadoDelPlazo.VENCIDO
    elif restantes <= UMBRAL_ALERTA_DIAS:
        situacion = EstadoDelPlazo.POR_VENCER
    else:
        situacion = EstadoDelPlazo.HOLGADO

    return Plazo(vence_el=vence_el, dias_habiles_restantes=max(0, restantes), estado=situacion)


def _habiles_entre(desde: datetime, hasta: datetime) -> int:
    """Días hábiles que quedan, contados sobre el calendario de Lima.

    Se comparan FECHAS locales y no instantes: al ejecutivo le importa cuántos
    días le quedan, no cuántas horas. Contar por horas haría que un plazo que
    vence mañana a las 09:00 apareciera como "0 días" a las 10:00 de hoy.
    """
    a, b = to_lima(desde).date(), to_lima(hasta).date()
    if b <= a:
        return 0
    dias = 0
    actual = a
    while actual < b:
        actual = actual.fromordinal(actual.toordinal() + 1)
        if actual.weekday() < 5:
            dias += 1
    return dias
