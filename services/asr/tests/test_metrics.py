"""Tests de la métrica de error de reconocimiento."""

from __future__ import annotations

from cea_asr import calcular_wer, normalizar


def test_las_tildes_no_son_errores_de_reconocimiento() -> None:
    """Un modelo que escribe "credito" no ha oído mal, ha escrito distinto."""
    assert calcular_wer("crédito", "credito").wer == 0.0
    assert calcular_wer("¿Cuánto?", "cuanto").wer == 0.0


def test_setiembre_y_septiembre_son_la_misma_palabra() -> None:
    """Ambas grafías son correctas y la primera es la habitual en Perú.

    Contarlo como error infla el WER y esconde los errores reales detrás de
    ruido ortográfico.
    """
    assert calcular_wer("del diez de setiembre", "del diez de septiembre").wer == 0.0


def test_distingue_el_tipo_de_error() -> None:
    """Inserciones y borrados exigen arreglos opuestos, aunque den el mismo WER.

    Un modelo que alucina palabras de más y otro que se come el final de cada
    frase pueden compartir la cifra global y no compartir nada más.
    """
    borrado = calcular_wer("uno dos tres cuatro", "uno dos tres")
    assert borrado.borrados == 1 and borrado.inserciones == 0

    insercion = calcular_wer("uno dos tres", "uno dos tres cuatro")
    assert insercion.inserciones == 1 and insercion.borrados == 0

    assert borrado.wer != insercion.wer  # distinto denominador, mismo error


def test_referencia_vacia_no_revienta() -> None:
    assert calcular_wer("", "algo").wer == 0.0


def test_normalizar_parte_en_palabras() -> None:
    assert normalizar("Son S/ 189.90, ¿correcto?") == ["son", "s", "189", "90", "correcto"]
