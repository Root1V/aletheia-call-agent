"""La política de disparo: cuándo el copiloto se calla.

Estas pruebas no verifican una optimización. Un copiloto que sugiere ante cada
turno llena la pantalla de tarjetas que el ejecutivo deja de leer, y una
herramienta que se deja de leer está desinstalada aunque siga corriendo.
"""

from __future__ import annotations

import pytest
from cea_contracts import Speaker
from cea_orchestrator.politica import ENFRIAMIENTO_S, MINIMO_PALABRAS, Politica


class Reloj:
    """Tiempo controlado. Sin esto la prueba del enfriamiento tardaría 6 s."""

    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t

    def avanzar(self, s: float) -> None:
        self.t += s


def _politica() -> tuple[Politica, Reloj]:
    reloj = Reloj()
    return Politica(_reloj=reloj), reloj


TURNO = "No reconozco este cargo de ciento ochenta y nueve soles en mi tarjeta"


def test_sugiere_ante_una_pregunta_del_cliente() -> None:
    politica, _ = _politica()
    assert politica.evaluar(Speaker.CUSTOMER, TURNO) is None


def test_nunca_sugiere_sobre_el_turno_del_ejecutivo() -> None:
    """El copiloto no le responde al ejecutivo, y tampoco lo analiza.

    Es la misma restricción que impide medir su emoción: el producto asiste al
    trabajador, no lo vigila.
    """
    politica, _ = _politica()
    motivo = politica.evaluar(Speaker.AGENT, TURNO)
    assert motivo == "turno del ejecutivo"


@pytest.mark.parametrize("texto", ["Sí.", "Ajá", "Ya, correcto", "Mmm ok gracias"])
def test_ignora_los_asentimientos(texto: str) -> None:
    politica, _ = _politica()
    motivo = politica.evaluar(Speaker.CUSTOMER, texto)
    assert motivo is not None
    assert "corto" in motivo


def test_el_turno_del_ejecutivo_no_cuenta_para_el_enfriamiento() -> None:
    politica, reloj = _politica()
    assert politica.evaluar(Speaker.CUSTOMER, TURNO) is None
    politica.anotar_emision()

    reloj.avanzar(1.0)
    # Que el ejecutivo hable no consume ni reinicia el enfriamiento.
    politica.evaluar(Speaker.AGENT, "Permítame revisar su cuenta un momento")

    reloj.avanzar(1.0)
    motivo = politica.evaluar(Speaker.CUSTOMER, TURNO)
    assert motivo is not None
    assert "enfriamiento" in motivo


def test_enfria_tras_emitir_y_vuelve_a_abrirse() -> None:
    politica, reloj = _politica()
    assert politica.evaluar(Speaker.CUSTOMER, TURNO) is None
    politica.anotar_emision()

    reloj.avanzar(ENFRIAMIENTO_S - 0.5)
    assert politica.evaluar(Speaker.CUSTOMER, TURNO) is not None

    reloj.avanzar(1.0)
    assert politica.evaluar(Speaker.CUSTOMER, TURNO) is None


def test_el_primer_turno_no_espera_enfriamiento() -> None:
    """Sin esto, la primera sugerencia de la llamada llegaría seis segundos tarde.

    `ultima_emision` arranca en 0, y compararlo con el reloj sin comprobar que
    hubo una emisión previa haría que el primer turno pareciera estar dentro
    del enfriamiento de una sugerencia que nunca existió.
    """
    politica, _ = _politica()
    assert politica.ultima_emision == 0.0
    assert politica.evaluar(Speaker.CUSTOMER, TURNO) is None


def test_el_umbral_de_palabras_es_el_declarado() -> None:
    politica, _ = _politica()
    justo = " ".join(["palabra"] * MINIMO_PALABRAS)
    una_menos = " ".join(["palabra"] * (MINIMO_PALABRAS - 1))
    assert politica.evaluar(Speaker.CUSTOMER, justo) is None
    politica.ultima_emision = 0.0
    assert politica.evaluar(Speaker.CUSTOMER, una_menos) is not None
