"""Tests de la redacción de datos sensibles.

El caso central no es "detecta un DNI escrito": eso lo hace cualquier expresión
regular. Es que en una llamada NADIE escribe su DNI, lo dicta, y entonces todo
detector convencional informa cero coincidencias mientras el número queda en
claro. Esa es la regresión que estos tests impiden.
"""

from __future__ import annotations

import pytest
from cea_contracts import PIIKind
from cea_redaction import (
    extraer_cadenas,
    luhn,
    parece_dictado_en_curso,
    redactar,
    redactar_parcial,
)

# Números de prueba publicados por las marcas: no corresponden a ninguna cuenta.
VISA = "4111111111111111"
MASTERCARD = "5555555555554444"

PALABRAS = {
    "0": "cero",
    "1": "uno",
    "2": "dos",
    "3": "tres",
    "4": "cuatro",
    "5": "cinco",
    "6": "seis",
    "7": "siete",
    "8": "ocho",
    "9": "nueve",
}


def dictar(numero: str) -> str:
    """Cómo suena un número leído en voz alta, tal como lo transcribe el ASR."""
    return ", ".join(PALABRAS[c] for c in numero)


# ── el caso que justifica todo el módulo ────────────────────────────────────


def test_un_dni_dictado_en_voz_alta_se_redacta() -> None:
    """Lo que el reconocedor entrega de verdad, no dígitos escritos.

    Verificado contra la salida real del ASR sobre audio sintetizado: el
    reconocedor devuelve las cifras como palabras separadas por comas.
    """
    texto = f"Claro, mi DNI es {dictar('45678912')}, ¿lo necesita?"

    r = redactar(texto)

    assert PIIKind.DNI in r.tipos
    assert "cuatro, cinco, seis" not in r.texto
    assert "[DNI]" in r.texto


def test_una_tarjeta_dictada_se_redacta_por_luhn() -> None:
    texto = f"Le doy el número completo: {dictar(VISA)}"

    r = redactar(texto)

    assert PIIKind.NUMERO_TARJETA in r.tipos
    assert "[N.º TARJETA]" in r.texto


def test_un_numero_escrito_tambien_se_redacta() -> None:
    """Un mismo turno puede mezclar ambas formas según decida el reconocedor."""
    r = redactar(f"Mi documento es 45678912 y la tarjeta {MASTERCARD}")

    assert PIIKind.DNI in r.tipos
    assert PIIKind.NUMERO_TARJETA in r.tipos


# ── lo que NO se puede tachar ────────────────────────────────────────────────


@pytest.mark.parametrize(
    "texto",
    [
        "Son ciento ochenta y nueve soles con noventa",
        "El consumo fue el diez de setiembre a las tres y media de la tarde",
        "Tengo dos tarjetas y tres cuentas",
        "La tarjeta termina en cuatro cinco dos uno",
        "Le respondemos en quince días hábiles",
    ],
)
def test_no_toca_lo_que_el_ejecutivo_necesita_leer(texto: str) -> None:
    """Una redacción que se come importes y fechas se acaba desactivando entera.

    Los importes se dicen como números compuestos ("ciento ochenta y nueve"),
    no cifra a cifra, y por eso no entran en el normalizador. Los últimos cuatro
    dígitos de una tarjeta se muestran a propósito: PCI-DSS lo permite y son lo
    que el cliente usa para identificar el plástico.
    """
    assert redactar(texto).texto == texto


def test_una_tirada_larga_sin_patron_se_tacha_igual() -> None:
    """Decisión conservadora y deliberada.

    Ante un número largo que el cliente dictó y no encaja en nada conocido, es
    preferible tacharlo a arriesgarse a que fuera una cuenta. El motivo queda
    registrado para poder revisar si genera ruido.
    """
    r = redactar(f"El código de la operación es {dictar('987654321098')}")

    assert PIIKind.NUMERO_CUENTA in r.tipos


# ── el código de seguridad, que sólo existe por contexto ─────────────────────


def test_el_cvv_se_reconoce_por_lo_que_lo_anuncia() -> None:
    """Tres dígitos sueltos no son nada; tres dígitos tras "código de seguridad" sí."""
    r = redactar("El código de seguridad es siete tres siete")

    assert PIIKind.CVV in r.tipos
    assert "siete tres siete" not in r.texto


def test_tres_digitos_sin_contexto_no_son_un_cvv() -> None:
    assert redactar("Somos tres cuatro dos personas en casa").texto.count("[") == 0


# ── parciales: la fuga que el turno final no evita ───────────────────────────


def test_un_dictado_a_medias_no_se_publica() -> None:
    """Publicar las hipótesis intermedias filtra el número cifra a cifra.

    Cada parcial por separado es inocuo —tres dígitos no encajan en nada— pero
    la secuencia completa habría pasado por el bus y por la pantalla antes de
    que el detector pudiera reconocerla.
    """
    for cifras in ("cuatro, uno, uno", "cuatro, uno, uno, uno", "cuatro, uno, uno, uno, uno"):
        assert redactar_parcial(f"el número es {cifras}") is None


def test_un_parcial_sin_dictado_si_se_publica() -> None:
    r = redactar_parcial("Buenos días, tengo un problema con un cargo")

    assert r is not None
    assert r.texto == "Buenos días, tengo un problema con un cargo"


def test_el_dictado_deja_de_retenerse_cuando_termina() -> None:
    """Si tras las cifras hay más palabras, el dictado acabó y ya se puede juzgar."""
    assert parece_dictado_en_curso(f"el número es {dictar(VISA)}")
    assert not parece_dictado_en_curso(f"el número es {dictar(VISA)} y ese es todo")


# ── piezas ───────────────────────────────────────────────────────────────────


def test_luhn_separa_tarjetas_de_cifras_cualesquiera() -> None:
    """Sin Luhn, cualquier número de pedido largo se tacharía como tarjeta."""
    assert luhn(VISA)
    assert luhn(MASTERCARD)
    assert not luhn("4532119876543210")
    assert not luhn("1234567890123456")


def test_las_comas_no_parten_la_cadena_dictada() -> None:
    """El reconocedor puntúa el dictado; partir ahí impediría reconocer el documento."""
    cadenas = extraer_cadenas("es cuatro, cinco, seis, siete, ocho, nueve, uno, dos")

    assert len(cadenas) == 1
    assert cadenas[0].digitos == "45678912"


def test_los_hallazgos_solapados_no_se_anidan() -> None:
    """Un PAN contiene tiradas que también parecen un DNI."""
    r = redactar(f"la tarjeta {dictar(VISA)}")

    assert len(r.hallazgos) == 1
    assert r.texto.count("[") == 1


def test_cada_hallazgo_explica_por_que() -> None:
    """Una redacción discutida tiene que poder defenderse ante un auditor."""
    r = redactar(f"mi DNI {dictar('45678912')}")

    assert all(h.motivo for h in r.hallazgos)
