"""Configuración del acceso a modelos."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class AjustesLLM(BaseSettings):
    """Credenciales y destino de la plataforma.

    Los nombres de las variables son los del propio SDK (`AXONIUM_*`) en lugar
    de inventar unos con prefijo propio: quien opera la plataforma ya los
    conoce, y tener dos juegos de nombres para el mismo secreto garantiza que
    algún día se configure el que no se lee.
    """

    model_config = SettingsConfigDict(env_prefix="AXONIUM_", env_file=".env", extra="ignore")

    client_id: str | None = None
    client_secret: str | None = None

    # Vacías por defecto: el SDK ya apunta al despliegue oficial y sólo hay que
    # fijarlas para uno autoalojado.
    auth_base_url: str | None = None
    gateway_base_url: str | None = None

    # El slug del modelo NO se escribe aquí con un valor por defecto plausible.
    #
    # Depende del despliegue y de lo que el token tenga concedido, así que un
    # valor inventado produce un fallo en tiempo de ejecución que parece un
    # problema de la plataforma. Sin configurar, el servicio consulta el
    # catálogo y lo dice.
    modelo: str | None = None

    timeout_s: float = 30.0

    @property
    def hay_credenciales(self) -> bool:
        return bool(self.client_id and self.client_secret)


@lru_cache
def obtener_ajustes() -> AjustesLLM:
    return AjustesLLM()
