"""Autenticación OIDC contra Keycloak.

Preparada para cuando el banco pida SSO corporativo. No se activa por defecto:
`CEA_AUTH_MODE=oidc` la selecciona, y entonces el navegador va a Keycloak y
vuelve con un token que esta API sólo verifica.
"""

from __future__ import annotations

import jwt
from fastapi import HTTPException, status
from jwt import PyJWKClient

from .base import AccessToken, AgentIdentity


class OidcAuthProvider:
    """Verifica tokens emitidos por Keycloak. Nunca ve la contraseña."""

    def __init__(self, issuer: str, audience: str) -> None:
        self._issuer = issuer
        self._audience = audience
        self._jwks: PyJWKClient | None = None

    @property
    def name(self) -> str:
        return "oidc"

    @property
    def supports_password_login(self) -> bool:
        return False

    async def password_login(self, username: str, password: str) -> AccessToken:
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED,
            "Con SSO corporativo el inicio de sesión ocurre en el proveedor de identidad, "
            "no en esta API. El portal debe redirigir al flujo de autorización.",
        )

    def _jwks_client(self) -> PyJWKClient:
        if self._jwks is None:
            self._jwks = PyJWKClient(f"{self._issuer}/protocol/openid-connect/certs")
        return self._jwks

    async def verify_token(self, token: str) -> AgentIdentity:
        try:
            key = self._jwks_client().get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                key.key,
                algorithms=["RS256"],
                audience=self._audience,
                issuer=self._issuer,
            )
        except jwt.PyJWTError as exc:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                f"Sesión inválida o expirada: {exc}",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc

        return AgentIdentity(
            agent_id=claims["sub"],
            username=claims.get("preferred_username", claims["sub"]),
            name=claims.get("name", ""),
            roles=frozenset(claims.get("realm_access", {}).get("roles", ())),
        )
