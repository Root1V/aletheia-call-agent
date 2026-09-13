"""Autenticación del portal.

Dos modos:

- ``oidc``: verificación real del token contra Keycloak. Es el único modo
  admisible fuera de la máquina del desarrollador.
- ``dev``: salta la verificación para que el MVP arranque sin configurar nada.

El modo ``dev`` es cómodo y por eso es peligroso: un despliegue que lo herede
por descuido deja el portal abierto. La aplicación se niega a arrancar en modo
dev si detecta que no está escuchando en localhost (ver ``main.py``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, status
from jwt import PyJWKClient

from .config import Settings, get_settings


@dataclass(slots=True, frozen=True)
class AgentIdentity:
    """Quién es el ejecutivo que tiene el workspace abierto."""

    agent_id: str
    name: str
    roles: frozenset[str]

    def require(self, role: str) -> None:
        if role not in self.roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Requiere el rol '{role}'")


_DEV_AGENT = AgentIdentity(
    agent_id="dev-ejecutivo",
    name="Ejecutivo de Demostración",
    roles=frozenset({"ejecutivo"}),
)

_jwks: PyJWKClient | None = None


def _jwks_client(settings: Settings) -> PyJWKClient:
    global _jwks
    if _jwks is None:
        _jwks = PyJWKClient(f"{settings.oidc_issuer}/protocol/openid-connect/certs")
    return _jwks


async def current_agent(
    authorization: Annotated[str | None, Header()] = None,
    settings: Annotated[Settings, Depends(get_settings)] = None,  # type: ignore[assignment]
) -> AgentIdentity:
    if settings.auth_mode == "dev":
        return _DEV_AGENT

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Falta el token de acceso")

    token = authorization.split(" ", 1)[1]
    try:
        signing_key = _jwks_client(settings).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.oidc_audience,
            issuer=settings.oidc_issuer,
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Token inválido: {exc}") from exc

    roles = claims.get("realm_access", {}).get("roles", [])
    return AgentIdentity(
        agent_id=claims.get("preferred_username", claims["sub"]),
        name=claims.get("name", ""),
        roles=frozenset(roles),
    )


CurrentAgent = Annotated[AgentIdentity, Depends(current_agent)]
