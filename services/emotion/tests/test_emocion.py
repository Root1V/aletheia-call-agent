"""Tests del motor de emoción.

Protegen las decisiones que costaron una reescritura: la referencia robusta y
la calibración del mapeo. Ambas fallaban produciendo números que PARECÍAN
razonables —barras que se movían, valores entre 0 y 1— mientras medían al
revés o en binario.
"""

from __future__ import annotations

import numpy as np
import pytest
from cea_emotion import MotorDeEmocion, SeñalesConversacionales
from cea_emotion.baseline import LineaBase
from cea_emotion.features import extraer

SR = 16000


def _voz(duracion_s: float, *, amplitud: float = 0.15, f0: float = 160.0) -> np.ndarray:
    """Señal con estructura de voz: armónicos y envolvente silábica.

    No es habla, pero tiene lo que el motor mide: periodicidad para el tono,
    energía para el volumen y una envolvente que enciende y apaga como las
    sílabas. Sintética a propósito, para poder variar UNA magnitud cada vez.
    """
    t = np.arange(int(SR * duracion_s)) / SR
    onda = sum(np.sin(2 * np.pi * f0 * k * t) / k for k in (1, 2, 3))
    envolvente = 0.6 + 0.4 * np.sin(2 * np.pi * 4.0 * t)
    return (onda * envolvente * amplitud).astype(np.float32)


def _correr(motor: MotorDeEmocion, audio: np.ndarray, conv=None, call="c"):
    paso = SR // 10
    ultimo = None
    for i in range(0, len(audio), paso):
        f = motor.procesar(call, audio[i : i + paso], conversacional=conv)
        if f is not None:
            ultimo = f
    return ultimo


@pytest.fixture
def motor() -> MotorDeEmocion:
    m = MotorDeEmocion(sample_rate=SR)
    m.abrir("c")
    # Calentamiento: el motor aprende cómo suena esta voz cuando no pasa nada.
    _correr(m, _voz(12.0))
    return m


def test_la_voz_de_referencia_no_dispara_las_barras(motor) -> None:
    """Hablar normal tiene que dar valores bajos, no medios."""
    f = _correr(motor, _voz(6.0))

    assert abs(f.arousal) < 0.35
    assert f.scores["frustracion"] < 0.4


def test_subir_la_voz_sube_la_activacion(motor) -> None:
    """Es la comprobación mínima, y la primera versión la fallaba al revés.

    Con media y varianza exponenciales, el salto de energía engordaba el
    denominador del z-score y el grito se enmascaraba a sí mismo: la activación
    BAJABA al gritar.
    """
    tranquilo = _correr(motor, _voz(4.0)).arousal
    alto = _correr(motor, _voz(4.0, amplitud=0.40)).arousal

    assert alto > tranquilo + 0.25, f"tranquilo={tranquilo:.3f} alto={alto:.3f}"


def test_la_escala_tiene_zona_intermedia(motor) -> None:
    """Una barra que sólo vale 0.05 o 0.95 es un interruptor, no un medidor.

    Con el centro en 1.5 y pendiente 1.2, un caso claramente activado ya daba
    0.98 y no quedaba margen para distinguir "molesto" de "furioso".
    """
    medio = _correr(motor, _voz(4.0, amplitud=0.26)).arousal
    extremo = _correr(motor, _voz(4.0, amplitud=0.60)).arousal

    assert 0.15 < medio < 0.85, f"el caso intermedio dio {medio:.3f}"
    assert extremo > medio


def test_el_silencio_no_tiene_emocion(motor) -> None:
    """No se puede leer el ánimo de quien no habla.

    La confianza cae y la UI pinta un guion en vez de un valor: mostrar la
    última emoción conocida durante el silencio haría creer al ejecutivo que el
    cliente sigue enfadado mientras escucha en calma.
    """
    f = _correr(motor, np.zeros(SR * 3, dtype=np.float32))

    assert f.confidence < 0.35


def test_la_valencia_se_declara_ausente(motor) -> None:
    """Ni "no medido" ni cero: `None`.

    La prosodia no distingue alegría de enfado —ambas suenan con energía y tono
    altos—. Un 0.0 se leería como "neutral", que es una afirmación que nadie ha
    hecho.
    """
    f = _correr(motor, _voz(3.0))

    assert f.valence is None
    assert "satisfaccion" not in f.scores
    assert "confusion" not in f.scores


def test_las_interrupciones_suben_la_frustracion(motor) -> None:
    """Señal conversacional que la prosodia no da por sí sola."""
    sin = _correr(motor, _voz(3.0), SeñalesConversacionales(0, 5)).scores["frustracion"]
    con = _correr(motor, _voz(3.0), SeñalesConversacionales(4, 5)).scores["frustracion"]

    assert con > sin + 0.15


def test_la_cadencia_de_salida_es_de_dos_por_segundo(motor) -> None:
    """El búfer conserva 2.5 s de contexto y su tamaño se queda fijo.

    Comparar contra él para decidir cuándo emitir hacía salir un fotograma por
    cada bloque de entrada: diez por segundo, inundando el bus con datos
    idénticos.
    """
    paso = SR // 10
    audio = _voz(10.0)
    emitidos = sum(
        1
        for i in range(0, len(audio), paso)
        if motor.procesar("c", audio[i : i + paso]) is not None
    )

    assert 18 <= emitidos <= 22, f"{emitidos} fotogramas en 10 s"


def test_la_referencia_resiste_un_valor_extremo() -> None:
    """Mediana y MAD, no media y desviación.

    Una sola palabra gritada durante el calentamiento no puede ensanchar la
    referencia hasta el punto de que nada posterior la supere.
    """
    linea = LineaBase()
    normales = [_voz(0.5, amplitud=0.15) for _ in range(11)]
    grito = _voz(0.5, amplitud=0.9)

    for a in [*normales[:5], grito, *normales[5:]]:
        linea.observar(extraer(a, SR))

    assert linea.lista
    # El centro debe seguir en la zona de la voz normal, no arrastrado al grito.
    assert linea.energia.centro < 0.3


def test_la_referencia_no_persigue_al_hablante(motor) -> None:
    """Un cliente que lleva dos minutos gritando no puede "normalizar" su grito.

    Con una media móvil sí ocurría: la barra volvía a cero justo cuando más
    importaba.
    """
    sostenido = [_correr(motor, _voz(4.0, amplitud=0.45)).arousal for _ in range(6)]

    assert sostenido[-1] > 0.3, (
        f"la activación decayó a {sostenido[-1]:.3f} tras el grito sostenido"
    )


def test_detecta_que_el_cliente_se_calma(motor) -> None:
    """El uso que importa es el cambio, y en ambos sentidos.

    Un cliente que se calma es tan informativo como uno que se altera: le dice
    al ejecutivo que lo que está haciendo funciona.
    """
    alterado = _correr(motor, _voz(4.0, amplitud=0.42)).arousal
    for _ in range(3):
        calmado = _correr(motor, _voz(4.0, amplitud=0.15)).arousal

    assert calmado < alterado - 0.3


def test_quien_entra_alterado_y_sigue_igual_se_lee_neutro() -> None:
    """Limitación conocida, verificada para que nadie la descubra en una demo.

    La referencia se aprende de los primeros segundos. Si esos segundos ya son
    de grito, el grito ES la referencia. Afirmar "este cliente está enfadado" en
    absoluto exigiría un modelo entrenado o una referencia poblacional; ninguna
    de las dos está todavía, y el panel lo dice.
    """
    motor = MotorDeEmocion(sample_rate=SR)
    motor.abrir("c")
    # Toda la llamada al mismo nivel alto: nunca hay contraste.
    _correr(motor, _voz(12.0, amplitud=0.45))
    f = _correr(motor, _voz(6.0, amplitud=0.45))

    assert abs(f.arousal) < 0.35, "se esperaba lectura neutra: sin contraste no hay señal de cambio"
