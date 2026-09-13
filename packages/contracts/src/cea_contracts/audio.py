"""Capa de ingesta de audio.

El audio NO viaja por el bus de eventos JSON: son tramas binarias a 50 Hz por
hablante, y serializarlas destruiría el presupuesto de latencia. Viajan
en proceso, del adaptador de ingesta a los servicios de voz.

Lo que sí es contrato es la INTERFAZ: el MVP usa tracks de LiveKit (separación
de hablantes exacta y gratuita, sin diarización), y la telefonía real llegará
por AudioSocket, mod_audio_fork o SIPREC sin que el pipeline cambie.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .enums import Speaker


@dataclass(slots=True, frozen=True)
class AudioFrame:
    """Una trama de PCM 16-bit mono de un solo hablante.

    Es un dataclass con slots y no un modelo Pydantic a propósito: se crean
    decenas de miles por llamada y la validación por trama no se paga sola.
    """

    call_id: str
    speaker: Speaker
    pcm16: bytes
    sample_rate: int
    ts_ms: int

    @property
    def duration_ms(self) -> float:
        # 2 bytes por muestra, mono.
        return len(self.pcm16) / 2 / self.sample_rate * 1000


@runtime_checkable
class AudioIngressAdapter(Protocol):
    """Fuente de audio de una llamada.

    Implementaciones previstas:

    - ``LiveKitTrackAdapter``    — MVP. Un track por participante: la separación
                                   de hablantes es exacta por construcción.
    - ``AudioSocketAdapter``     — Asterisk. slin16 en tramas de 20 ms.
    - ``ModAudioForkAdapter``    — FreeSWITCH.
    - ``SiprecAdapter``          — SBC vía drachtio/OpenSIPS + rtpengine.
    - ``FileReplayAdapter``      — CRÍTICO. Reproduce WAV guionados; es la base
                                   de los tests de regresión y de las
                                   evaluaciones deterministas.

    Advertencia que vale para todas las de telefonía real: entregan 8 kHz μ-law,
    no 16 kHz de micrófono. Todos los modelos de voz degradan ahí, y por eso las
    evaluaciones usan audio decimado a 8 kHz desde el primer día.
    """

    @property
    def call_id(self) -> str: ...

    def frames(self) -> AsyncIterator[AudioFrame]:
        """Tramas de audio de ambos hablantes, etiquetadas, en orden de llegada."""
        ...

    async def aclose(self) -> None: ...
