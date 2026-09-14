"""Tests del acceso a modelos.

No requieren credenciales ni plataforma viva: cubren la configuración y el
comportamiento ante su ausencia, que es justo lo que alguien encuentra la
primera vez que intenta arrancar esto en otra máquina.
"""

from __future__ import annotations

import pytest
from cea_llm import AjustesLLM, AxoniumProvider, CredencialesFaltantes, Mensaje


def test_sin_credenciales_falla_diciendo_cuales_faltan() -> None:
    """Un fallo de configuración tiene que nombrar la variable que falta.

    "Faltan las credenciales" manda a alguien a leer código; nombrar
    AXONIUM_CLIENT_ID lo manda a resolverlo.
    """
    proveedor = AxoniumProvider(AjustesLLM(client_id=None, client_secret=None))

    with pytest.raises(CredencialesFaltantes) as exc:
        proveedor._construir()  # noqa: SLF001 - se comprueba el mensaje, no el flujo

    mensaje = str(exc.value)
    assert "AXONIUM_CLIENT_ID" in mensaje
    assert "AXONIUM_CLIENT_SECRET" in mensaje
    # Y que el resto del producto no depende de esto.
    assert "el resto del portal funciona" in mensaje


def test_las_credenciales_a_medias_cuentan_como_ausentes() -> None:
    """Sólo el id, o sólo el secreto, no sirve de nada.

    Sin esta comprobación el SDK fallaría más adentro con un error de
    autenticación, que parece un problema de la plataforma y no de la
    configuración local.
    """
    assert not AjustesLLM(client_id="algo", client_secret=None).hay_credenciales
    assert not AjustesLLM(client_id=None, client_secret="algo").hay_credenciales
    assert AjustesLLM(client_id="a", client_secret="b").hay_credenciales


def test_no_hay_un_slug_de_modelo_escrito_por_defecto() -> None:
    """Los slugs dependen del despliegue y de lo que el token tenga concedido.

    Un valor por defecto plausible produce un fallo en ejecución que parece de
    la plataforma. Vacío, el servicio consulta el catálogo y lo dice.
    """
    assert AjustesLLM().modelo is None


def test_las_urls_vacias_no_pisan_el_destino_del_sdk() -> None:
    """El SDK ya apunta a la plataforma; pasarle None explícito lo rompería."""
    ajustes = AjustesLLM(client_id="a", client_secret="b")

    assert ajustes.auth_base_url is None
    assert ajustes.gateway_base_url is None


def test_los_mensajes_se_convierten_al_formato_del_gateway() -> None:
    convertidos = AxoniumProvider._a_wire(  # noqa: SLF001
        [Mensaje("system", "Eres un asistente"), Mensaje("user", "Hola")]
    )

    assert convertidos == [
        {"role": "system", "content": "Eres un asistente"},
        {"role": "user", "content": "Hola"},
    ]


def test_el_razonamiento_va_separado_de_la_respuesta() -> None:
    """Material de auditoría, no de pantalla.

    Una sugerencia se juzga por lo que dice y por la fuente que cita, no por el
    monólogo que la precedió; mezclarlos haría que el ejecutivo leyera en voz
    alta el borrador del modelo.
    """
    from cea_llm import Respuesta

    r = Respuesta(
        texto="La comisión es de S/ 45.00", razonamiento="El usuario pregunta…", modelo="m"
    )

    assert "usuario pregunta" not in r.texto
    assert r.razonamiento
