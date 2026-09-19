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

    espera_maxima_s: float = 2.0
    """Cuánto se deja que el SDK espere DENTRO de una llamada antes de rendirse.

    El valor por defecto del SDK es 60 s, que es correcto para un proceso por
    lotes y desastroso aquí. Ante un 429 la plataforma devuelve un `Retry-After`
    de hasta lo que quede de ventana, y el SDK lo respeta: la sugerencia acaba
    llegando medio minuto después, cuando la conversación ya pasó por otros dos
    turnos. **Una sugerencia que llega tarde es peor que ninguna**: el ejecutivo
    la lee, no encaja con lo que el cliente acaba de decir, y a la tercera vez
    deja de mirar el panel.

    Con dos segundos, una espera que no cabe en el presupuesto de la sugerencia
    sale como error en lugar de dormirse, el copiloto publica una tarjeta
    bloqueada con su motivo, y el ejecutivo sabe que el copiloto se calló a
    propósito. El propio SDK lo documenta así: por encima de este tope el error
    llega al llamante con su `retry_after` para que decida él.
    """

    @property
    def hay_credenciales(self) -> bool:
        return bool(self.client_id and self.client_secret)


@lru_cache
def obtener_ajustes() -> AjustesLLM:
    return AjustesLLM()
