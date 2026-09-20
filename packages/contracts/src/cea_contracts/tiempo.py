"""Zona horaria del perímetro.

Todo se ALMACENA en UTC y se MUESTRA en America/Lima (UTC-5, sin horario de
verano). Mezclar ambas cosas produce el error más vergonzoso posible en una
demo bancaria peruana: un consumo hecho a las 20:25 aparece como "01:25 del día
siguiente", y cualquiera en la sala lo nota antes que el ejecutivo.

El mismo cuidado aplica al plazo regulatorio: los 15 días hábiles de la Ley
31763 se cuentan sobre el calendario local, no sobre UTC.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

LIMA = ZoneInfo("America/Lima")


def to_lima(dt: datetime) -> datetime:
    """Convierte a hora de Lima para mostrar."""
    return dt.astimezone(LIMA)


def fmt_fecha_hora(dt: datetime) -> str:
    """dd/mm HH:MM en hora de Lima."""
    return to_lima(dt).strftime("%d/%m %H:%M")


def fmt_fecha(dt: datetime) -> str:
    """dd/mm en hora de Lima."""
    return to_lima(dt).strftime("%d/%m")


def habiles_despues(desde: datetime, dias: int) -> datetime:
    """Suma días HÁBILES sobre el calendario de Lima.

    El plazo de la Ley 31763 es en días hábiles, no corridos: calcularlo como
    corridos adelanta el vencimiento y llena el panel de alarmas falsas, que es
    la forma más rápida de que el ejecutivo deje de mirar los relojes de plazo.

    El cómputo va sobre la fecha LOCAL, no sobre UTC: un reclamo presentado un
    viernes a las 20:00 de Lima es de viernes, aunque en UTC ya sea sábado.

    No contempla feriados peruanos. Eso exige el calendario oficial, que cambia
    cada año y se publica por decreto, y queda anotado como deuda: hoy el plazo
    calculado es siempre igual o MÁS corto que el real, que es el lado seguro
    del error.
    """
    actual = to_lima(desde)
    restantes = dias
    while restantes > 0:
        actual += timedelta(days=1)
        if actual.weekday() < 5:
            restantes -= 1
    return actual.astimezone(UTC)
