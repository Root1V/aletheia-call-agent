"""Configuración de la API.

Todo por variable de entorno, con valores por defecto que funcionan contra
`infra/docker-compose.yml` sin configurar nada. El objetivo de la Fase 0 es que
`docker compose up` + `make dev` arranquen sin un archivo .env.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CEA_", env_file=".env", extra="ignore")

    database_url: str = "postgresql://cea:cea_dev@localhost:5432/cea"
    redis_url: str = "redis://localhost:6380/0"

    # El Redis de la plataforma Prometheus ocupa el 6379 en esta máquina, por
    # eso el puerto por defecto es 6380 (ver infra/.env).

    livekit_url: str = "ws://localhost:7880"
    livekit_api_key: str = "devkey"
    livekit_api_secret: str = "devsecret_solo_para_desarrollo_local_32chars"

    # ── autenticación ────────────────────────────────────────────────────────
    #
    # "dev" salta la verificación de token para que el MVP arranque sin
    # configurar Keycloak. "oidc" es el modo real y el único admisible en
    # cualquier entorno compartido: la API se niega a arrancar en modo dev si
    # detecta que no está en local (ver main.py).
    auth_mode: Literal["dev", "oidc"] = "dev"
    oidc_issuer: str = "http://localhost:8089/realms/cea"
    oidc_audience: str = "cea-web"

    cors_origins: tuple[str, ...] = ("http://localhost:5180", "http://127.0.0.1:5180")

    # Presupuesto de latencia. No es decorativo: la API lo expone en /health
    # para que el panel de Grafana y los tests de carga comparen contra el
    # mismo número, y un p95 fuera de presupuesto se trata como bug.
    budget_transcript_ms: int = 700
    budget_suggestion_ms: int = 1500


@lru_cache
def get_settings() -> Settings:
    return Settings()
