"""Construcción del prompt de la sugerencia.

Dos decisiones que vienen de haberlo probado contra la plataforma:

1. Se le pide EXPLÍCITAMENTE la frase que el ejecutivo dirá en voz alta. Sin
   esa instrucción el modelo devuelve una tarea para el ejecutivo —"verificar
   si el cliente tiene historial"— que no sirve de nada leída al cliente.

2. Se le prohíbe aportar datos que no estén en el material. El modelo redacta
   bien y por eso inventa con fluidez: en la primera prueba real escribió "una
   tarifa legítima por los 6 viajes" cuando eran 189 soles de un solo cargo.
   La instrucción no basta —para eso están los guardarraíles— pero reduce la
   frecuencia.
"""

from __future__ import annotations

from dataclasses import dataclass

from cea_llm import Mensaje
from cea_rag import Pasaje

SISTEMA = """\
Eres el copiloto de un ejecutivo de atención telefónica de un banco peruano.

Devuelve ÚNICAMENTE la frase que el ejecutivo debe decirle al cliente en voz \
alta. No des instrucciones al ejecutivo, no expliques tu razonamiento, no \
saludes ni te despidas, no uses comillas.

Reglas:
- Máximo 40 palabras, una o dos frases.
- Trata al cliente de usted.
- Usa EXCLUSIVAMENTE los datos del material que se te entrega. Si un dato no \
está ahí, no lo menciones.
- No inventes cifras ni las combines entre sí: no sumes, no promedies, no \
calcules.
- No prometas aprobaciones, devoluciones ni resultados de un reclamo.
- Si el material no alcanza para responder, di que se va a verificar.\
"""


@dataclass(slots=True, frozen=True)
class Contexto:
    """Todo lo que el modelo puede usar. Nada más entra al prompt."""

    turno_del_cliente: str
    datos_de_la_llamada: str
    pasajes: tuple[Pasaje, ...]

    def material(self) -> str:
        """El material tal como lo ve el modelo.

        Es también lo que reciben los guardarraíles: si algo no está aquí, la
        sugerencia que lo mencione no tiene respaldo por definición.
        """
        partes = [f"DATOS DE LA LLAMADA:\n{self.datos_de_la_llamada}"]
        for i, p in enumerate(self.pasajes, 1):
            titulo = f"{p.documento} § {p.section}" if p.section else p.documento
            partes.append(f"DOCUMENTO {i} ({titulo}):\n{p.contenido}")
        return "\n\n".join(partes)


def construir(ctx: Contexto) -> list[Mensaje]:
    return [
        Mensaje("system", SISTEMA),
        Mensaje(
            "user",
            f"{ctx.material()}\n\n"
            f"EL CLIENTE ACABA DE DECIR:\n{ctx.turno_del_cliente}\n\n"
            f"Escribe la frase que el ejecutivo debe responderle.",
        ),
    ]
