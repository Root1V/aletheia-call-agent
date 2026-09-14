"""Proveedor sobre el SDK de Axonium (plataforma Prometheus)."""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator

from axonium import AsyncAxonium, AxoniumError

from .base import Catalogo, EsfuerzoRazonamiento, Fragmento, Mensaje, ProveedorLLM, Respuesta
from .config import AjustesLLM, obtener_ajustes

log = logging.getLogger("cea.llm")


def _motivo_de_fin(completion) -> str | None:
    """Motivo por el que paró la generación.

    Vive en `choices[0]`, no en la completion. Leerlo del sitio equivocado no
    lanza nada: `getattr` devuelve None, `truncada` sale siempre False y una
    respuesta cortada a mitad de una cifra —"la comisión es de cuarenta y
    cin"— pasa por buena.
    """
    opciones = getattr(completion, "choices", None) or []
    if not opciones:
        return None
    return getattr(opciones[0], "finish_reason", None)


class CredencialesFaltantes(RuntimeError):
    """Se intentó generar sin credenciales configuradas."""

    def __init__(self) -> None:
        super().__init__(
            "Faltan las credenciales de la plataforma. Definir AXONIUM_CLIENT_ID y "
            "AXONIUM_CLIENT_SECRET, que emite el operador de la plataforma. "
            "Sin ellas el copiloto no genera: el resto del portal funciona igual."
        )


class AxoniumProvider(ProveedorLLM):
    """Acceso a los modelos locales de la plataforma Prometheus."""

    def __init__(self, ajustes: AjustesLLM | None = None) -> None:
        self._ajustes = ajustes or obtener_ajustes()
        self._cliente: AsyncAxonium | None = None
        self._catalogo: Catalogo | None = None

    @property
    def nombre(self) -> str:
        return "axonium"

    def _construir(self) -> AsyncAxonium:
        if not self._ajustes.hay_credenciales:
            raise CredencialesFaltantes
        if self._cliente is None:
            # Sólo se pasan las URL si están fijadas. El SDK ya apunta al
            # despliegue oficial, y enviarle None explícito sobrescribiría ese
            # valor por defecto con nada.
            extra = {}
            if self._ajustes.auth_base_url:
                extra["auth_base_url"] = self._ajustes.auth_base_url
            if self._ajustes.gateway_base_url:
                extra["gateway_base_url"] = self._ajustes.gateway_base_url
            self._cliente = AsyncAxonium(
                client_id=self._ajustes.client_id,
                client_secret=self._ajustes.client_secret,
                **extra,
            )
        return self._cliente

    async def aclose(self) -> None:
        if self._cliente is not None:
            await self._cliente.aclose()
            self._cliente = None

    async def catalogo(self) -> Catalogo:
        """Modelos que este token puede invocar.

        Se cachea tras la primera consulta: los slugs no cambian dentro de una
        sesión y pedirlo en cada generación añadiría una ida y vuelta al camino
        crítico de la sugerencia.
        """
        if self._catalogo is not None:
            return self._catalogo
        cliente = self._construir()
        mios = await cliente.models.mine()
        self._catalogo = Catalogo(slugs=tuple(mios.ids))
        return self._catalogo

    async def _resolver_modelo(self, modelo: str | None) -> str:
        elegido = modelo or self._ajustes.modelo
        if elegido:
            return elegido
        # Sin slug configurado se toma el primero del catálogo y se deja dicho
        # en el log. Es preferible a fallar: en desarrollo permite arrancar sin
        # saberse los slugs de memoria, y el aviso evita que esa comodidad se
        # cuele en un despliegue.
        cat = await self.catalogo()
        if not cat.slugs:
            raise RuntimeError(
                "El token no tiene ningún modelo concedido. Consultar con el operador "
                "de la plataforma qué slugs están autorizados para este cliente."
            )
        log.warning(
            "AXONIUM_MODELO sin definir: se usa %r del catálogo. Fijarlo antes de desplegar.",
            cat.slugs[0],
        )
        return cat.slugs[0]

    @staticmethod
    def _a_wire(
        mensajes: list[Mensaje], esfuerzo: EsfuerzoRazonamiento | None = None
    ) -> list[dict[str, str]]:
        """Convierte al formato del gateway, anteponiendo el esfuerzo si se pide.

        La instrucción va como mensaje de sistema propio y al principio, que es
        la convención que estos modelos entienden. Mezclarla en el prompt del
        usuario no la respetan.
        """
        salida = [{"role": m.rol, "content": m.contenido} for m in mensajes]
        if esfuerzo:
            salida.insert(0, {"role": "system", "content": f"Reasoning: {esfuerzo}"})
        return salida

    async def completar(
        self,
        mensajes: list[Mensaje],
        *,
        modelo: str | None = None,
        max_tokens: int = 512,
        temperatura: float = 0.2,
        esfuerzo: EsfuerzoRazonamiento | None = None,
    ) -> Respuesta:
        cliente = self._construir()
        slug = await self._resolver_modelo(modelo)
        inicio = time.perf_counter()
        try:
            completion = await cliente.chat.completions.create(
                model=slug,
                messages=self._a_wire(mensajes, esfuerzo),
                max_tokens=max_tokens,
                temperature=temperatura,
            )
        except AxoniumError:
            # No se envuelve ni se traga: la jerarquía de errores del SDK
            # distingue un fallo de autenticación de un modelo caído o de un
            # límite de cuota, y quien llama necesita esa diferencia para saber
            # si reintentar, avisar al operador o seguir sin copiloto.
            raise

        uso = getattr(completion, "usage", None)
        return Respuesta(
            texto=completion.content or "",
            razonamiento=getattr(completion, "reasoning", None) or None,
            modelo=slug,
            tokens_entrada=getattr(uso, "prompt_tokens", None),
            tokens_salida=getattr(uso, "completion_tokens", None),
            latencia_ms=round((time.perf_counter() - inicio) * 1000, 1),
            truncada=_motivo_de_fin(completion) == "length",
        )

    async def transmitir(
        self,
        mensajes: list[Mensaje],
        *,
        modelo: str | None = None,
        max_tokens: int = 512,
        temperatura: float = 0.2,
        esfuerzo: EsfuerzoRazonamiento | None = None,
    ) -> AsyncIterator[Fragmento]:
        cliente = self._construir()
        slug = await self._resolver_modelo(modelo)
        async with cliente.chat.completions.stream(
            model=slug,
            messages=self._a_wire(mensajes, esfuerzo),
            max_tokens=max_tokens,
            temperature=temperatura,
        ) as flujo:
            async for chunk in flujo:
                # Un fragmento lleva razonamiento o respuesta, nunca ambos: la
                # UI puede así distinguir "está pensando" de "ya contesta" sin
                # inferirlo de que el texto venga vacío.
                yield Fragmento(
                    texto=chunk.content or "",
                    razonamiento=getattr(chunk, "reasoning", "") or "",
                )
