"""Contrato de acceso a modelos de lenguaje.

El resto del sistema habla con este protocolo y nunca con el SDK. No es
ceremonia: la capa generativa toca el copiloto, la clasificación de reclamos y
el resumen post-llamada, y si el tipo del proveedor se filtrase a los tres,
cambiar de plataforma dejaría de ser una decisión y pasaría a ser una
reescritura.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable

Rol = Literal["system", "user", "assistant"]


@dataclass(slots=True, frozen=True)
class Mensaje:
    rol: Rol
    contenido: str


@dataclass(slots=True, frozen=True)
class Respuesta:
    """Lo que devuelve una generación completa."""

    texto: str
    modelo: str
    tokens_entrada: int | None = None
    tokens_salida: int | None = None
    latencia_ms: float | None = None

    razonamiento: str | None = None
    """Cadena de pensamiento de los modelos que la producen.

    Va separada del texto a propósito. Es material de depuración y auditoría,
    NO se le muestra al ejecutivo: una sugerencia se juzga por lo que dice y por
    la fuente que cita, no por el monólogo que la precedió.
    """

    truncada: bool = False
    """Si la generación se cortó por límite de longitud.

    Importa más de lo que parece: una respuesta truncada puede terminar a mitad
    de una cifra —"la comisión es de cuarenta y cin"— y eso no se puede mostrar.
    """


@dataclass(slots=True)
class Fragmento:
    """Un trozo de respuesta en streaming."""

    texto: str = ""
    razonamiento: str = ""


@dataclass(slots=True, frozen=True)
class Catalogo:
    """Modelos que este token puede invocar."""

    slugs: tuple[str, ...] = field(default=())

    def tiene(self, slug: str) -> bool:
        return slug in self.slugs


@runtime_checkable
class ProveedorLLM(Protocol):
    """Puerto de generación."""

    @property
    def nombre(self) -> str: ...

    async def catalogo(self) -> Catalogo:
        """Slugs disponibles para este token.

        Es la única fuente de verdad sobre qué modelos existen: dependen del
        despliegue y de lo que el token tenga concedido, así que cualquier lista
        escrita en el código envejece mal.
        """
        ...

    async def completar(
        self,
        mensajes: list[Mensaje],
        *,
        modelo: str,
        max_tokens: int = 512,
        temperatura: float = 0.2,
    ) -> Respuesta: ...

    def transmitir(
        self,
        mensajes: list[Mensaje],
        *,
        modelo: str,
        max_tokens: int = 512,
        temperatura: float = 0.2,
    ) -> AsyncIterator[Fragmento]:
        """Genera en streaming.

        Existe como método aparte y no como una bandera porque en el gateway
        exige otro permiso y nunca se reintenta de forma automática: un
        reintento aquí es una generación nueva y facturable, no una repetición.
        """
        ...
