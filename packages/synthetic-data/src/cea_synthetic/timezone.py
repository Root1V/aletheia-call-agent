"""Zona horaria del perímetro.

Todo se ALMACENA en UTC y se MUESTRA en America/Lima (UTC-5, sin horario de
verano). Mezclar ambas cosas produce el error más vergonzoso posible en una
demo bancaria peruana: un consumo hecho a las 20:25 aparece como "01:25 del día
siguiente", y cualquiera en la sala lo nota antes que el ejecutivo.

El mismo cuidado aplica al plazo regulatorio: los 15 días hábiles de la Ley
31763 se cuentan sobre el calendario local, no sobre UTC.

La implementación vive en `cea_contracts.tiempo`. Estuvo copiada en tres sitios
—generador, API y copiloto— y tres copias de una conversión de zona horaria son
tres oportunidades de que una se quede con la zona equivocada.
"""

from cea_contracts.tiempo import LIMA, fmt_fecha, fmt_fecha_hora, to_lima

__all__ = ["LIMA", "fmt_fecha", "fmt_fecha_hora", "to_lima"]
