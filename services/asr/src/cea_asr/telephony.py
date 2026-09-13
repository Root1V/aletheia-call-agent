"""Degradación de audio a calidad telefónica.

La telefonía real entrega 8 kHz con compresión µ-law, no los 16 kHz limpios de
un micrófono. Ese paso destruye todo lo que hay por encima de 4 kHz y sube el
error de reconocimiento de forma medible: sobre este modelo y este corpus, el
WER pasa de 3.3% a 6.7%.

Por eso las evaluaciones se corren sobre audio degradado desde el primer día.
Medir con audio de micrófono produce un número que se ve bien en una
presentación y que no se parece a lo que pasará en producción.
"""

from __future__ import annotations

# audioop desapareció de la biblioteca estándar en Python 3.13; el backport
# audioop-lts conserva el nombre del módulo, así que el import es el mismo.
import audioop  # type: ignore[import-not-found]

import numpy as np

TASA_TELEFONIA = 8000


def degradar_a_telefonia(pcm16: bytes, sample_rate: int = 16000) -> bytes:
    """16 kHz -> 8 kHz -> µ-law -> 8 kHz -> tasa original.

    El viaje de ida y vuelta es deliberado: no basta con submuestrear, porque
    lo que más daña la señal es la cuantización logarítmica de µ-law. Volver a
    la tasa original permite alimentar el mismo reconocedor sin cambiarle la
    configuración, aislando el efecto del canal.
    """
    a_8k, _ = audioop.ratecv(pcm16, 2, 1, sample_rate, TASA_TELEFONIA, None)
    comprimido = audioop.lin2ulaw(a_8k, 2)
    expandido = audioop.ulaw2lin(comprimido, 2)
    de_vuelta, _ = audioop.ratecv(expandido, 2, 1, TASA_TELEFONIA, sample_rate, None)
    return de_vuelta


def pcm16_a_float32(pcm16: bytes) -> np.ndarray:
    """PCM entero de 16 bits a flotante en [-1, 1], que es lo que espera el modelo."""
    return np.frombuffer(pcm16, dtype=np.int16).astype(np.float32) / 32768.0


def float32_a_pcm16(muestras: np.ndarray) -> bytes:
    recortado = np.clip(muestras, -1.0, 1.0)
    return (recortado * 32767.0).astype(np.int16).tobytes()
