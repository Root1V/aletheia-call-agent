"""Verificación de cifras: el control que evita el incidente regulatorio.

La regla es estricta a propósito: toda cantidad que aparezca en el texto
generado tiene que estar en el material que se le dio al modelo o en la tabla de
cifras citables. Una cifra compuesta por el modelo no pasa, aunque sea la suma
correcta de dos que sí le dimos.
"""

from __future__ import annotations

import pytest
from cea_copilot import extraer_cantidades, verificar

CONTEXTO = (
    "- Cargo en discusión: S/ 1450.00 · comercio real AliExpress · 16/09 10:44\n"
    "- El cliente tiene 6 compras previas en ese comercio en los últimos 90 días."
)
TARIFARIO = [(45.0, "pen"), (15.0, "dias_habiles"), (5.0, "porcentaje")]


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("S/ 1450.00", 1450.0),
        ("S/ 1,450.00", 1450.0),
        ("S/ 12,345.67", 12345.67),
        ("S/ 45.00", 45.0),
        ("S/ 189.90", 189.9),
        ("son 1450 soles", 1450.0),
    ],
)
def test_los_importes_de_cuatro_cifras_se_leen_enteros(texto: str, esperado: float) -> None:
    """El fallo que motivó estas pruebas, y era grave en las DOS direcciones.

    El patrón anterior exigía separador de miles, así que de "S/ 1450.00"
    extraía **145**: bloqueaba una cifra correcta, y —lo peor— del contexto no
    extraía nada, de modo que un texto que dijera "S/ 145" con el importe real en
    1450 habría pasado la verificación. Aprobar una cifra equivocada es justo lo
    que este módulo existe para impedir.

    Importes de cuatro cifras son cotidianos en banca peruana: el escenario de
    fraude son S/ 1,450.00.
    """
    valores = [c.valor for c in extraer_cantidades(texto)]
    assert esperado in valores


def test_una_cifra_del_contexto_se_aprueba() -> None:
    v = verificar("El consumo de S/ 1450.00 en AliExpress no fue reconocido.", CONTEXTO, TARIFARIO)
    assert v.aprobada, v.motivo


def test_una_cifra_que_no_esta_se_bloquea() -> None:
    v = verificar("El consumo de S/ 145.00 en AliExpress no fue reconocido.", CONTEXTO, TARIFARIO)
    assert not v.aprobada
    assert "145" in v.motivo


def test_el_mismo_valor_escrito_de_otra_forma_se_aprueba() -> None:
    """«S/ 1450.00» y «1450 soles» son la misma cifra dicha de dos maneras.

    El resumen de la llamada y el modelo no coinciden en el formato, y tratarlos
    como cantidades distintas bloqueaba textos correctos.
    """
    assert verificar("Fueron 1450 soles.", CONTEXTO, TARIFARIO).aprobada


def test_un_porcentaje_nunca_casa_con_un_importe() -> None:
    """45 y 45% no son la misma cifra, y confundirlos en un tarifario es un incidente."""
    v = verificar("La comisión es del 1450% del monto.", CONTEXTO, TARIFARIO)
    assert not v.aprobada


def test_una_cifra_del_tarifario_se_aprueba_aunque_no_este_en_el_contexto() -> None:
    assert verificar("La membresía anual cuesta S/ 45.00.", CONTEXTO, TARIFARIO).aprobada


def test_el_modelo_no_puede_componer_una_cifra_sumando_dos_que_si_le_dimos() -> None:
    """Aunque la suma sea correcta. 1450 + 45 = 1495, y 1495 no se le dio."""
    v = verificar("El total asciende a S/ 1495.00.", CONTEXTO, TARIFARIO)
    assert not v.aprobada


def test_las_horas_y_fechas_no_son_cantidades() -> None:
    """«las 15:37 del 10/09» disparaba la verificación por el 37 de los minutos.

    Un control que se come respuestas buenas acaba desactivado.
    """
    v = verificar("El cargo se hizo el 10/09 a las 15:37.", CONTEXTO, TARIFARIO)
    assert v.aprobada, v.motivo


def test_un_importe_con_decimales_no_se_confunde_con_una_hora() -> None:
    """La hora se reconoce sólo por los dos puntos.

    Aceptar el punto —"15.37"— eximiría de verificación a "S/ 31.65" y
    "S/ 52.00", que es lo contrario de lo que hace falta.
    """
    v = verificar("La comisión es de S/ 31.65.", CONTEXTO, TARIFARIO)
    assert not v.aprobada
