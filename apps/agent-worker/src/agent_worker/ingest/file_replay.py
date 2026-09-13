"""Reproducción de un guion grabado como si fuera una llamada en vivo.

Es el adaptador más importante del proyecto, aunque no sea el que verá un
cliente. Da lo que la telefonía real no da: una llamada IDÉNTICA cada vez.
Sobre eso se apoyan los tests de regresión, la evaluación del reconocimiento y
la posibilidad de depurar un fallo sin tener que reproducirlo hablando por
teléfono con la esperanza de decir lo mismo.

Respeta el ritmo original —silencios incluidos— porque el sistema depende de
las pausas: la detección de fin de turno es exactamente eso.
"""

from __future__ import annotations

import asyncio
import time
import wave
from collections.abc import AsyncIterator
from pathlib import Path

import yaml
from cea_asr import degradar_a_telefonia
from cea_contracts import AudioFrame, Speaker

# Tamaño de trama. Veinte milisegundos es lo que entregan Asterisk y
# FreeSWITCH, así que el pipeline se ejercita con el mismo grano que tendrá en
# producción en vez de con bloques cómodos que esconden problemas de ritmo.
TRAMA_MS = 20


class FileReplayAdapter:
    """Reproduce el audio de un escenario respetando su cronología."""

    def __init__(
        self,
        call_id: str,
        directorio: Path | str,
        *,
        velocidad: float = 1.0,
        telefonia: bool = False,
    ) -> None:
        self._call_id = call_id
        self._dir = Path(directorio)
        manifiesto_path = self._dir / "manifiesto.yaml"
        if not manifiesto_path.exists():
            raise FileNotFoundError(f"No hay manifiesto en {self._dir}. Ejecutar `make audio`.")
        self._manifiesto = yaml.safe_load(manifiesto_path.read_text())
        # >1 acelera; se usa en los tests para no esperar setenta segundos por
        # cada ejecución. En la demo se deja en 1.0 porque el ritmo ES el
        # comportamiento que se quiere mostrar.
        self._velocidad = velocidad
        self._telefonia = telefonia

    @property
    def call_id(self) -> str:
        return self._call_id

    @property
    def scenario_id(self) -> str:
        return self._manifiesto["scenario_id"]

    @property
    def sample_rate(self) -> int:
        return self._manifiesto["sample_rate"]

    @property
    def turnos(self) -> list[dict]:
        return self._manifiesto["turnos"]

    async def frames(self) -> AsyncIterator[AudioFrame]:
        sr = self.sample_rate
        muestras_por_trama = int(sr * TRAMA_MS / 1000)
        bytes_por_trama = muestras_por_trama * 2
        silencio = b"\x00" * bytes_por_trama
        inicio = time.perf_counter()
        reloj_ms = 0

        for turno in self.turnos:
            hablante = Speaker(turno["speaker"])
            otro = Speaker.AGENT if hablante is Speaker.CUSTOMER else Speaker.CUSTOMER

            # La pausa entre intervenciones se emite como silencio real en
            # AMBOS canales. Saltársela rompería la detección de fin de turno,
            # que es precisamente lo que mide esos silencios.
            for _ in range(int(turno["pausa_antes_ms"] / TRAMA_MS)):
                reloj_ms += TRAMA_MS
                await self._esperar(inicio, reloj_ms)
                yield AudioFrame(self._call_id, hablante, silencio, sr, reloj_ms)
                yield AudioFrame(self._call_id, otro, silencio, sr, reloj_ms)

            with wave.open(turno["wav"]) as w:
                pcm = w.readframes(w.getnframes())
            if self._telefonia:
                pcm = degradar_a_telefonia(pcm, sr)

            for offset in range(0, len(pcm), bytes_por_trama):
                trama = pcm[offset : offset + bytes_por_trama]
                if len(trama) < bytes_por_trama:
                    trama = trama + b"\x00" * (bytes_por_trama - len(trama))
                reloj_ms += TRAMA_MS
                await self._esperar(inicio, reloj_ms)
                yield AudioFrame(self._call_id, hablante, trama, sr, reloj_ms)
                # El canal del otro hablante sigue existiendo y está en
                # silencio. Emitirlo no es un detalle decorativo: es lo que
                # permite que su reconocedor acumule silencio y cierre su turno
                # anterior, igual que ocurre con dos tracks reales.
                yield AudioFrame(self._call_id, otro, silencio, sr, reloj_ms)

    async def _esperar(self, inicio: float, reloj_ms: int) -> None:
        """Espera hasta que el reloj de pared alcance la posición del audio."""
        objetivo = inicio + (reloj_ms / 1000) / self._velocidad
        retraso = objetivo - time.perf_counter()
        if retraso > 0:
            await asyncio.sleep(retraso)

    async def aclose(self) -> None:
        return None
