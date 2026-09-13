"""Autenticación local: JWT propio con contraseñas bcrypt."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext

from ..db import cursor
from .base import AccessToken, AgentIdentity

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Hash descartable con el que comparar cuando el usuario no existe.
#
# Sin esto, un usuario inexistente responde en microsegundos y uno real tarda
# los ~200 ms de bcrypt: esa diferencia basta para enumerar cuentas válidas
# cronometrando las respuestas. Verificando siempre contra algo, el costo es el
# mismo en ambos casos.
_HASH_SEÑUELO = _pwd.hash("contraseña-que-nadie-usa")

CREDENCIALES_INVALIDAS = HTTPException(
    status.HTTP_401_UNAUTHORIZED,
    # Mensaje deliberadamente genérico: no distingue usuario inexistente de
    # contraseña incorrecta ni de cuenta desactivada.
    detail="Usuario o contraseña incorrectos",
    headers={"WWW-Authenticate": "Bearer"},
)


def hash_password(plain: str) -> str:
    return _pwd.hash(plain)


class LocalAuthProvider:
    """JWT firmado por esta misma API, contra la tabla `users`."""

    def __init__(self, secret: str, *, algorithm: str = "HS256", ttl_hours: int = 9) -> None:
        self._secret = secret
        self._algorithm = algorithm
        # Nueve horas: un turno completo más margen. Más corto obliga a
        # reautenticar en mitad de una llamada con un cliente en línea, que es
        # el peor momento posible para pedirle credenciales a alguien.
        self._ttl = timedelta(hours=ttl_hours)

    @property
    def name(self) -> str:
        return "local"

    @property
    def supports_password_login(self) -> bool:
        return True

    async def password_login(self, username: str, password: str) -> AccessToken:
        async with cursor() as cur:
            await cur.execute(
                """
                SELECT user_id, username, full_name, password_hash, roles, is_active
                FROM users WHERE lower(username) = lower(%s)
                """,
                (username,),
            )
            row = await cur.fetchone()

        hash_a_verificar = row["password_hash"] if row else _HASH_SEÑUELO
        password_ok = _pwd.verify(password, hash_a_verificar)

        if row is None or not password_ok or not row["is_active"]:
            raise CREDENCIALES_INVALIDAS

        async with cursor() as cur:
            await cur.execute(
                "UPDATE users SET last_login_at = now() WHERE user_id = %s", (row["user_id"],)
            )

        identity = AgentIdentity(
            agent_id=row["user_id"],
            username=row["username"],
            name=row["full_name"],
            roles=frozenset(row["roles"]),
        )
        return AccessToken(
            token=self._emit(identity),
            expires_in=int(self._ttl.total_seconds()),
            identity=identity,
        )

    def _emit(self, identity: AgentIdentity) -> str:
        ahora = datetime.now(UTC)
        return jwt.encode(
            {
                "sub": identity.agent_id,
                "preferred_username": identity.username,
                "name": identity.name,
                "roles": sorted(identity.roles),
                "iat": int(ahora.timestamp()),
                "exp": int((ahora + self._ttl).timestamp()),
                "iss": "cea-api",
            },
            self._secret,
            algorithm=self._algorithm,
        )

    async def verify_token(self, token: str) -> AgentIdentity:
        try:
            claims = jwt.decode(token, self._secret, algorithms=[self._algorithm], issuer="cea-api")
        except JWTError as exc:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                f"Sesión inválida o expirada: {exc}",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc

        return AgentIdentity(
            agent_id=claims["sub"],
            username=claims.get("preferred_username", claims["sub"]),
            name=claims.get("name", ""),
            roles=frozenset(claims.get("roles", ())),
        )
