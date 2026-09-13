"""Contrato del reconocimiento de voz.

El resto del sistema habla con este protocolo y no con un motor concreto. Es lo
que permite cambiar de modelo —o de licencia de modelo— sin tocar el pipeline
ni la UI.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import numpy as np
from cea_contracts import Speaker


@dataclass(slots=True, frozen=True)
class Hypothesis:
    """Texto reconocido hasta ahora para un turno."""

    speaker: Speaker
    turn_id: str
    text: str
    is_final: bool
    started_at_ms: int
    ended_at_ms: int | None = None


@runtime_checkable
class StreamingASR(Protocol):
    """Reconocedor que emite hipótesis mientras el audio llega.

    Una instancia atiende varias llamadas y varios hablantes a la vez: el
    estado de decodificación vive por `(call_id, speaker)`, no en el objeto.
    """

    @property
    def name(self) -> str: ...

    @property
    def sample_rate(self) -> int: ...

    def open(self, call_id: str, speaker: Speaker) -> None:
        """Prepara el estado de un hablante de una llamada."""
        ...

    def accept(self, call_id: str, speaker: Speaker, samples: np.ndarray) -> Iterator[Hypothesis]:
        """Consume audio y emite las hipótesis que hayan cambiado."""
        ...

    def close(self, call_id: str, speaker: Speaker) -> Iterator[Hypothesis]:
        """Cierra el turno en curso y emite la hipótesis final."""
        ...
