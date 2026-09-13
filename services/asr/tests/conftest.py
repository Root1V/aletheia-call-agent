"""Fixtures del servicio de reconocimiento.

Los tests necesitan el modelo descargado (`make models`) y el audio guionado
(`make audio`). Si falta alguno, se omiten en vez de fallar: no todo el mundo
que toca el repositorio necesita 124 MB de pesos para corregir una consulta SQL.
"""

from __future__ import annotations

from pathlib import Path

import pytest

MODELO = Path("models/sherpa-onnx-streaming-zipformer-es-kroko-2025-08-06")
AUDIO = Path("evals/audio/disputa_cargo_no_reconocido")

requiere_modelo = pytest.mark.skipif(
    not MODELO.exists(), reason="Falta el modelo de voz. Ejecutar `make models`."
)
requiere_audio = pytest.mark.skipif(
    not (AUDIO / "manifiesto.yaml").exists(),
    reason="Falta el audio guionado. Ejecutar `make audio`.",
)


@pytest.fixture(scope="session")
def asr():
    from cea_asr import SherpaStreamingASR

    return SherpaStreamingASR(MODELO)
