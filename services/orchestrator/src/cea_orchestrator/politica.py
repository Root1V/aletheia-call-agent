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

import time
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

        transcurrido = self._ahora() - self.ultima_emision
        if self.ultima_emision and transcurrido < ENFRIAMIENTO_S:
            return f"enfriamiento ({transcurrido:.1f}s de {ENFRIAMIENTO_S:.0f}s)"

        return None

    def anotar_emision(self) -> None:
        self.ultima_emision = self._ahora()

    def _ahora(self) -> float:
        return self._reloj()  # type: ignore[operator]
