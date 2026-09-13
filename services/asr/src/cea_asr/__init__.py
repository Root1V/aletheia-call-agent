"""Reconocimiento de voz del copiloto."""

from .base import Hypothesis, StreamingASR
from .metrics import ResultadoWER, calcular_wer, normalizar
from .models import MODELOS, ModeloDeVoz, resumen_de_licencias
from .sherpa import COLA_DE_SILENCIO_MS, SherpaStreamingASR
from .telephony import degradar_a_telefonia, float32_a_pcm16, pcm16_a_float32

__all__ = [
    "COLA_DE_SILENCIO_MS",
    "MODELOS",
    "Hypothesis",
    "ModeloDeVoz",
    "ResultadoWER",
    "calcular_wer",
    "normalizar",
    "SherpaStreamingASR",
    "StreamingASR",
    "degradar_a_telefonia",
    "float32_a_pcm16",
    "pcm16_a_float32",
    "resumen_de_licencias",
]
