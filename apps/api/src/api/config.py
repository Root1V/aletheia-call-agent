"""Configuración de la API.

Todo por variable de entorno, con valores por defecto que funcionan contra
`infra/docker-compose.yml` sin configurar nada.
"""

from __future__ import annotations

import secrets
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# Secreto de desarrollo, reconocible a simple vista.
#
# Va como constante con nombre y no como una cadena cualquiera para que el
# arranque pueda detectarlo y negarse a usarlo fuera de desarrollo. Un secreto
# de firma filtrado permite emitir tokens válidos para cualquier usuario, con
# cualquier rol.
SECRETO_DE_DESARROLLO = "cambiar-este-secreto-antes-de-cualquier-despliegue"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CEA_", env_file=".env", extra="ignore")

    environment: Literal["dev", "staging", "prod"] = "dev"

    database_url: str = "postgresql://cea:cea_dev@localhost:5432/cea"
    redis_url: str = "redis://localhost:6380/0"
    # El Redis de la plataforma Prometheus ocupa el 6379 en esta máquina, por
    # eso el puerto por defecto es 6380 (ver infra/.env).

    livekit_url: str = "ws://localhost:7880"
    livekit_api_key: str = "devkey"
    livekit_api_secret: str = "devsecret_solo_para_desarrollo_local_32chars"

    # ── autenticación ────────────────────────────────────────────────────────
    #
    # "local": JWT propio contra la tabla `users`. Es el modo actual.
    # "oidc":  Keycloak, para cuando el banco integre su SSO corporativo.
    auth_mode: Literal["local", "oidc"] = "local"

    jwt_secret: str = SECRETO_DE_DESARROLLO
    jwt_ttl_hours: int = 9

    oidc_issuer: str = "http://localhost:8089/realms/cea"
    oidc_audience: str = "cea-web"

    cors_origins: tuple[str, ...] = ("http://localhost:5180", "http://127.0.0.1:5180")

    # Presupuesto de latencia. No es decorativo: la API lo expone en /health
    # para que el panel de Grafana, los tests de carga y las evaluaciones
    # comparen contra el mismo número, y un p95 fuera de presupuesto se trata
    # como bug.
    budget_transcript_ms: int = 700
    budget_suggestion_ms: int = 1500

    def validar_para_arranque(self) -> list[str]:
        """Problemas de configuración que deben impedir el arranque.

        Se devuelven todos juntos en vez de fallar en el primero: quien está
        preparando un despliegue prefiere ver la lista completa antes que
        descubrirlos de a uno.
        """
        problemas: list[str] = []
        if self.environment != "dev" and self.jwt_secret == SECRETO_DE_DESARROLLO:
            problemas.append(
                "CEA_JWT_SECRET sigue siendo el de desarrollo. Con ese secreto público "
                "cualquiera puede firmar un token válido para cualquier usuario y con "
                f"cualquier rol. Generar uno con: {generar_secreto()!r}"
            )
        if self.environment != "dev" and self.jwt_secret and len(self.jwt_secret) < 32:
            problemas.append("CEA_JWT_SECRET es demasiado corto: mínimo 32 caracteres.")
        return problemas


def generar_secreto() -> str:
    return secrets.token_urlsafe(48)


@lru_cache
def get_settings() -> Settings:
    return Settings()
