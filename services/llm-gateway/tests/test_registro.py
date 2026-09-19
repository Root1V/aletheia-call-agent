"""Una espera de la plataforma no puede quedarse sin imprimir.

El fallo que esto evita ya ocurrió: reporté al equipo de plataforma un "cuelgue
de 42 s" que era un 429 con `Retry-After`, esperado correctamente por el SDK y
registrado por él a INFO. Mi proceso tenía la raíz en WARNING, así que la línea
se descartaba y la llamada parecía colgada.
"""

from __future__ import annotations

import logging

import pytest
from cea_llm import REGISTRO_SDK, asegurar_visibilidad_de_esperas


@pytest.fixture(autouse=True)
def registro_limpio():
    """Devuelve el registro del SDK a su estado inicial entre pruebas."""
    sdk = logging.getLogger(REGISTRO_SDK)
    nivel, manejadores, propaga = sdk.level, list(sdk.handlers), sdk.propagate
    raiz = logging.getLogger()
    nivel_raiz, manejadores_raiz = raiz.level, list(raiz.handlers)
    yield
    sdk.level, sdk.propagate = nivel, propaga
    sdk.handlers[:] = manejadores
    raiz.level = nivel_raiz
    raiz.handlers[:] = manejadores_raiz


def _emitiria(registro: logging.Logger, nivel: int) -> bool:
    """¿Llegaría un registro de ese nivel a algún manejador?"""
    if not registro.isEnabledFor(nivel):
        return False
    actual: logging.Logger | None = registro
    while actual is not None:
        if actual.handlers:
            return True
        actual = actual.parent if actual.propagate else None
    return False


def test_con_la_raiz_en_warning_la_espera_se_veria_igual() -> None:
    """El caso exacto del informe equivocado."""
    raiz = logging.getLogger()
    raiz.handlers[:] = []
    raiz.setLevel(logging.WARNING)
    sdk = logging.getLogger(REGISTRO_SDK)
    sdk.handlers[:] = []
    sdk.setLevel(logging.NOTSET)
    sdk.propagate = True

    assert not _emitiria(sdk, logging.INFO), "la prueba no reproduce el fallo original"

    asegurar_visibilidad_de_esperas()

    assert _emitiria(sdk, logging.INFO)


def test_no_toca_el_nivel_de_la_raiz() -> None:
    """La API corre en WARNING a propósito; importar algo no puede cambiárselo."""
    raiz = logging.getLogger()
    raiz.handlers[:] = []
    raiz.setLevel(logging.WARNING)

    asegurar_visibilidad_de_esperas()

    assert raiz.level == logging.WARNING


def test_si_la_raiz_ya_imprime_no_se_duplica() -> None:
    """Un proceso con `basicConfig(INFO)` no debe ver cada espera dos veces."""
    raiz = logging.getLogger()
    raiz.handlers[:] = [logging.StreamHandler()]
    raiz.setLevel(logging.INFO)
    sdk = logging.getLogger(REGISTRO_SDK)
    sdk.handlers[:] = []
    sdk.propagate = True

    asegurar_visibilidad_de_esperas()

    assert sdk.handlers == []
    assert sdk.propagate is True


def test_llamarla_dos_veces_no_duplica_manejadores() -> None:
    raiz = logging.getLogger()
    raiz.handlers[:] = []
    raiz.setLevel(logging.WARNING)
    sdk = logging.getLogger(REGISTRO_SDK)
    sdk.handlers[:] = []

    asegurar_visibilidad_de_esperas()
    asegurar_visibilidad_de_esperas()

    assert len(sdk.handlers) == 1
