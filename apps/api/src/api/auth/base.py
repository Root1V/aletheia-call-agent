"""Contrato de autenticación.

Dos implementaciones intercambiables detrás del mismo protocolo:

- ``local``: JWT propio con contraseñas bcrypt. Es el modo del MVP.
- ``oidc``:  Keycloak. Es lo que un banco suele exigir cuando llega el momento
  de integrarse al SSO corporativo con MFA y políticas auditables.

Tenerlas detrás de un protocolo evita el trabajo que normalmente duele al
migrar: el resto de la aplicación depende de ``AgentIdentity``, no de cómo se
obtuvo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from fastapi import HTTPException, status


@dataclass(slots=True, frozen=True)
class AgentIdentity:
    """Quién tiene el workspace abierto.

    Es lo único que el resto de la aplicación conoce sobre la autenticación.
    """

    agent_id: str
    username: str
    name: str
    roles: frozenset[str]

    def require(self, role: str) -> None:
        if role not in self.roles:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Esta acción requiere el rol '{role}'",
            )


@dataclass(slots=True, frozen=True)
class AccessToken:
    token: str
    expires_in: int
    """Segundos hasta la expiración. El frontend lo usa para renovar a tiempo."""

    identity: AgentIdentity


@runtime_checkable
class AuthProvider(Protocol):
    """Puerto de autenticación."""

    @property
    def name(self) -> str: ...

    @property
    def supports_password_login(self) -> bool:
        """Si acepta usuario y contraseña contra este propio servicio.

        Es False en OIDC: ahí el navegador va a Keycloak y vuelve con un
        token, y nuestra API nunca ve la contraseña. Esa diferencia es
        justamente la razón de que el endpoint de login tenga que preguntar en
        vez de asumir.
        """
        ...

    async def password_login(self, username: str, password: str) -> AccessToken:
        """Valida credenciales y emite un token.

        Debe lanzar 401 con un mensaje GENÉRICO ante cualquier fallo: usuario
        inexistente, contraseña incorrecta o cuenta desactivada. Distinguirlos
        convierte el login en un oráculo para enumerar cuentas válidas.
        """
        ...

    async def verify_token(self, token: str) -> AgentIdentity: ...
