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


@pytest.mark.parametrize(
    "texto",
    [
        "De acuerdo, gracias por la ayuda",
        "No, eso era todo. Muchas gracias.",
        "Sí, claro, perfecto, muy amable, muchas gracias",
        "Buenos días, muchas gracias señorita",
        "Listo, entendido, muchas gracias, hasta luego",
        "Ya está, muchas gracias por su tiempo",
    ],
)
def test_no_sugiere_sobre_un_cierre_de_cortesia(texto: str) -> None:
    """Es donde el modelo confabula, y el daño es directo.

    Todos los casos pasan de cinco palabras a propósito: si fueran más cortos
    los silenciaría el umbral de longitud y la prueba pasaría sin ejercitar nada
    del filtro de cierre — verde por el motivo equivocado, que es peor que roja.

    Medido sobre una llamada real: ante "De acuerdo, gracias por la ayuda" el
    modelo escribió tres veces de tres «le informo que se ha generado el folio
    correspondiente para atender su reclamo». No existe tal folio —el registro
    de casos está en el backlog— y el ejecutivo se lo habría dicho al cliente.

    Los guardarraíles la bloquearon las tres veces, pero el arreglo correcto es
    no pedirla: un modelo sin material contesta igual, y lo que inventa cuando no
    tiene nada que decir es justo lo que más daño hace.
    """
    politica, _ = _politica()
    motivo = politica.evaluar(Speaker.CUSTOMER, texto)
    assert motivo is not None
    assert "cortesía" in motivo or "cierre" in motivo


@pytest.mark.parametrize(
    "texto",
    [
        "Está bien, y el dinero me lo devuelven",
        "Gracias, pero quiero saber cuánto cuesta la membresía",
        "No estoy de acuerdo con esa comisión",
        "Ah, ya caigo, fui al aeropuerto, disculpe la molestia",
    ],
)
def test_una_formula_de_cortesia_no_silencia_lo_que_viene_detras(texto: str) -> None:
    """El filtro de cierre no puede comerse una pregunta real.

    "Está bien, ¿y el dinero me lo devuelven?" empieza con una fórmula y es la
    pregunta más importante de una disputa. Un criterio que contara las palabras
    sobrantes la silenciaba —quedan dos—, y por eso el cierre se reconoce por
    VOCABULARIO: sólo calla si TODO lo que dice el turno es cortesía.
    """
    politica, _ = _politica()
    assert politica.evaluar(Speaker.CUSTOMER, texto) is None


def test_las_listas_se_comparan_normalizadas() -> None:
    """La trampa silenciosa: "señorita" llega como "senorita".

    El turno se normaliza a ASCII antes de comparar, así que una lista escrita
    con eñe o con tilde no casa nunca. La palabra parece estar y no está, y sólo
    se descubre probando.
    """
    from cea_orchestrator.politica import _CIERRE

    assert "senorita" in _CIERRE
    assert "señorita" not in _CIERRE
