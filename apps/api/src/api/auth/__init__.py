"""Autenticación del portal: selección de proveedor y dependencia de FastAPI."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from ..config import get_settings
from .base import AccessToken, AgentIdentity, AuthProvider
from .local import LocalAuthProvider, hash_password
from .oidc import OidcAuthProvider

__all__ = [
    "AccessToken",
    "AgentIdentity",
    "AuthProvider",
    "CurrentAgent",
    "current_agent",
    "get_auth_provider",
    "hash_password",
]


@lru_cache
def get_auth_provider() -> AuthProvider:
    settings = get_settings()
    if settings.auth_mode == "oidc":
        return OidcAuthProvider(settings.oidc_issuer, settings.oidc_audience)
    return LocalAuthProvider(settings.jwt_secret, ttl_hours=settings.jwt_ttl_hours)


async def current_agent(
    authorization: Annotated[str | None, Header()] = None,
) -> AgentIdentity:
    """Ejecutivo autenticado.

    No hay modo que salte la verificación. Un interruptor de "desarrollo" que
    devuelve un usuario ficticio es cómodo justo hasta el día en que se hereda
    a un entorno compartido y deja el portal abierto; el bootstrap por script
    hace que no haga falta.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Falta el token de acceso",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.split(" ", 1)[1].strip()
    return await get_auth_provider().verify_token(token)


CurrentAgent = Annotated[AgentIdentity, Depends(current_agent)]
