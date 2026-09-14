"""Tests de los controles sobre la sugerencia.

Son la parte del copiloto que decide si una frase puede llegar a los labios del
ejecutivo. Cada test cubre un caso observado en generaciones reales contra la
plataforma, no un supuesto.
"""

from __future__ import annotations

import pytest
from cea_copilot import Bloqueo, evaluar, extraer_cantidades, verificar

CONTEXTO = (
    "Cargo de S/ 189.90 el 10/09 a las 15:37, descriptor SUNRISE TECH. Comercio real inDrive, "
    "transporte. El cliente tiene 6 compras previas en inDrive en 90 días desde su "
    "propio teléfono. "
    "El texto del estado de cuenta lo define el procesador de pagos del comercio."
)
HECHOS = [(45.0, "pen"), (15.0, "dias_habiles"), (25.0, "pen")]


def _evaluar(texto: str):
    return evaluar(texto, contexto=CONTEXTO, hechos=HECHOS, hay_pasajes=True)


# ── cifras ───────────────────────────────────────────────────────────────────


def test_bloquea_una_cifra_compuesta_por_el_modelo() -> None:
    """El caso observado: el modelo divide un importe entre un conteo.

    S/ 31.65 es exactamente 189.90 entre 6. Es aritméticamente correcto y
    factualmente falso: las seis compras previas no tienen relación con el
    importe de esta. Que una cifra se pueda derivar de otras dos no la
    convierte en un dato.
    """
    r = _evaluar("El cargo de S/ 189.90 son 6 viajes de S/ 31.65 cada uno en inDrive.")

    assert not r.aprobada
    assert Bloqueo.CIFRA_NO_VERIFICADA in r.bloqueos
    assert "31.65" in r.motivo


def test_bloquea_una_comision_que_no_esta_en_el_tarifario() -> None:
    r = _evaluar("La comisión de mantenimiento de su tarjeta es de S/ 52.00 anuales.")

    assert not r.aprobada
    assert Bloqueo.CIFRA_NO_VERIFICADA in r.bloqueos


def test_acepta_una_cifra_del_tarifario() -> None:
    r = _evaluar("La comisión de mantenimiento de la tarjeta es de S/ 45.00 anuales.")

    assert Bloqueo.CIFRA_NO_VERIFICADA not in r.bloqueos


@pytest.mark.parametrize(
    "texto",
    [
        "El cargo de S/ 189.90 del 10/09 a las 15:37 corresponde a inDrive.",
        "El cargo del 14 de setiembre de 2026 por S/ 189.90 es de inDrive.",
        "Su documento ***4521 es correcto; el cargo de S/ 189.90 es de inDrive.",
    ],
)
def test_las_horas_y_fechas_no_son_cifras_citables(texto: str) -> None:
    """Bloquear una sugerencia CORRECTA es como fallar hacia el lado caro.

    Los minutos de "15:37" hacían saltar la verificación por un "37" que no es
    ninguna cantidad. Un control que se come respuestas buenas termina
    desactivado, y entonces no protege de nada.
    """
    r = _evaluar(texto)

    assert Bloqueo.CIFRA_NO_VERIFICADA not in r.bloqueos, r.motivo


def test_la_hora_se_reconoce_solo_por_los_dos_puntos() -> None:
    """Aceptar el punto como separador horario exime a los importes.

    "S/ 31.65" y "S/ 52.00" encajan en el patrón de una hora escrita con punto,
    y quedarían fuera de la verificación: exactamente lo contrario de lo que
    hace falta.
    """
    cantidades = {c.valor for c in extraer_cantidades("son S/ 31.65 a las 15:37")}

    assert 31.65 in cantidades
    assert 37.0 not in cantidades


def test_45_y_45_00_son_la_misma_comision() -> None:
    assert verificar("son S/ 45", "", [(45.00, "pen")]).aprobada


# ── frases prohibidas ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "texto",
    [
        "Le garantizo que le vamos a aprobar la devolución.",
        "Le aseguro que le devolveremos el dinero esta semana.",
        "Este fondo tiene rentabilidad asegurada.",
        "Le conviene invertir ese dinero en nuestro fondo mutuo.",
    ],
)
def test_bloquea_compromisos_que_el_banco_no_puede_hacer(texto: str) -> None:
    """No es cuestión de estilo.

    Prometer una rentabilidad o garantizar un resultado crea una expectativa
    exigible y expone al banco ante la SBS y ante Indecopi.
    """
    assert Bloqueo.FRASE_PROHIBIDA in _evaluar(texto).bloqueos


# ── destinatario ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "texto",
    [
        "Verificar si el cliente tiene historial de compras en inDrive.",
        "El ejecutivo debe confirmar el descriptor con el cliente.",
        "Se recomienda revisar los consumos previos del cliente.",
    ],
)
def test_bloquea_lo_que_esta_escrito_para_el_ejecutivo(texto: str) -> None:
    """Observado con un prompt flojo contra la plataforma.

    Una tarjeta que le dice al ejecutivo lo que ya sabe no vale nada, y leída
    en voz alta al cliente es absurda.
    """
    assert Bloqueo.INSTRUCCION_AL_EJECUTIVO in _evaluar(texto).bloqueos


# ── respaldo documental ──────────────────────────────────────────────────────


def test_bloquea_lo_que_no_esta_en_el_material() -> None:
    """No mide veracidad, mide procedencia.

    Una frase cuyas palabras no aparecen en ningún pasaje recuperado ni en los
    datos de la llamada se la inventó entera.
    """
    r = _evaluar("Nuestras oficinas centrales están en San Isidro y abrimos los domingos.")

    assert Bloqueo.SIN_RESPALDO_DOCUMENTAL in r.bloqueos


def test_sin_pasajes_no_hay_sugerencia() -> None:
    """Si la búsqueda no encontró nada, no hay nada que citar."""
    r = evaluar("Cualquier cosa.", contexto="", hechos=[], hay_pasajes=False)

    assert Bloqueo.SIN_RESPALDO_DOCUMENTAL in r.bloqueos


def test_una_respuesta_vacia_se_bloquea_como_tal() -> None:
    """Distinguirla importa: el portal debe decir que el modelo no contestó,
    no que la respuesta fuera inadecuada."""
    r = evaluar("   ", contexto=CONTEXTO, hechos=HECHOS, hay_pasajes=True)

    assert r.bloqueos == (Bloqueo.VACIA,)


def test_una_sugerencia_correcta_pasa_los_tres_controles() -> None:
    r = _evaluar(
        "El cargo de S/ 189.90 corresponde a inDrive; el descriptor SUNRISE TECH "
        "lo define el procesador de pagos del comercio."
    )

    assert r.aprobada, r.motivo
    assert r.cobertura > 0.6
