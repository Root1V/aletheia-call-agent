"""Zona horaria del perímetro.

Todo se ALMACENA en UTC y se MUESTRA en America/Lima (UTC-5, sin horario de
verano). Mezclar ambas cosas produce el error más vergonzoso posible en una
demo bancaria peruana: un consumo hecho a las 20:25 aparece como "01:25 del día
siguiente", y cualquiera en la sala lo nota antes que el ejecutivo.

El mismo cuidado aplica al plazo regulatorio: los 15 días hábiles de la Ley
31763 se cuentan sobre el calendario local, no sobre UTC.
"""

from __future__ import annotations

from datetime import datetime
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
