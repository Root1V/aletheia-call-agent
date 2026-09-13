"""Formato de fechas en hora de Lima.

Se almacena en UTC y se muestra en America/Lima. Mezclar ambas cosas hace que
un consumo de las 20:25 aparezca como "01:25 del día siguiente", que es el
detalle que delata una demo bancaria peruana en el primer vistazo.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

LIMA = ZoneInfo("America/Lima")


def to_lima(dt: datetime) -> datetime:
    return dt.astimezone(LIMA)


def fmt_fecha_hora(dt: datetime) -> str:
    return to_lima(dt).strftime("%d/%m %H:%M")


def fmt_fecha(dt: datetime) -> str:
    return to_lima(dt).strftime("%d/%m")
