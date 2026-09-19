"""Que una espera de la plataforma nunca sea invisible.

Existe por un fallo concreto y caro de diagnosticar. Reporté al equipo de
plataforma un "cuelgue esporádico de 42 s" en una petición que normalmente
tarda 345 ms. No había ningún cuelgue: era un 429 por límite de peticiones, y
el SDK estaba esperando el `Retry-After` que la propia plataforma devolvía —que
es lo correcto—. El SDK lo registraba, además, a INFO y con el número de
segundos.

Lo que fallaba era mío: el script de medición no configuraba el registro, así
que la raíz estaba en WARNING y sin manejadores, y ese INFO se descartaba.
Desde fuera, una llamada de 36 s sin una sola línea en el log parece
exactamente un cuelgue. Verificado: el registro decía
`Waiting before a retry delay_s=36.0 status=429` y no se imprimía.

De ahí que esto no sea un ajuste de comodidad. Un proceso que habla con la
plataforma y NO enseña sus esperas produce informes de fallo equivocados, que
cuestan tiempo a tres equipos. Se llama desde todos los puntos de entrada.
"""

from __future__ import annotations

import logging

# El registro del SDK. Sus esperas y sus reintentos salen por aquí.
REGISTRO_SDK = "axonium"


def asegurar_visibilidad_de_esperas(nivel: int = logging.INFO) -> None:
    """Garantiza que las esperas del SDK se vean, aunque la raíz esté en WARNING.

    No toca la configuración de la raíz: un proceso que ya decidió su nivel
    —la API corre con `--log-level warning` a propósito— no debería encontrarse
    con que importar una biblioteca se lo cambia. Lo que hace es dejar el
    registro del SDK en INFO con su propio manejador cuando no hay ninguno que
    vaya a imprimirlo.

    Es idempotente: llamarla dos veces no duplica líneas.
    """
    registro = logging.getLogger(REGISTRO_SDK)
    registro.setLevel(min(registro.level or nivel, nivel))

    raiz = logging.getLogger()
    # Si la raíz ya imprime a este nivel, la propagación basta y añadir un
    # manejador aquí duplicaría cada línea.
    if raiz.handlers and raiz.getEffectiveLevel() <= nivel:
        return

    if any(getattr(h, "_cea_esperas", False) for h in registro.handlers):
        return

    manejador = logging.StreamHandler()
    manejador.setLevel(nivel)
    manejador.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    manejador._cea_esperas = True  # type: ignore[attr-defined]
    registro.addHandler(manejador)
    registro.propagate = False
