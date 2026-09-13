"""Pipeline de una llamada: audio → reconocimiento → bus de eventos.

Un worker por llamada. El estado vive en el proceso mientras dura la llamada y
lo duradero se publica como eventos; así el worker puede caerse y reiniciarse
sin arrastrar estado a medias.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

import numpy as np
from cea_asr import StreamingASR, pcm16_a_float32
from cea_bus import EventBus
from cea_contracts import (
    AsrFinal,
    AsrPartial,
    AudioFrame,
    CallEnded,
    CallStarted,
    Speaker,
    TurnEnded,
)

log = logging.getLogger("cea.worker")

# Audio que se acumula antes de entregárselo al reconocedor.
#
# El adaptador entrega tramas de 20 ms, que es el grano de la telefonía, pero
# decodificar cada 20 ms multiplica por cinco las llamadas al modelo sin que el
# texto cambie con esa frecuencia. Cien milisegundos es el punto donde el coste
# baja y el retraso sigue siendo imperceptible.
BLOQUE_MS = 100


@dataclass(slots=True)
class _Acumulador:
    """Junta tramas de un hablante hasta completar un bloque."""

    objetivo: int
    partes: list[np.ndarray] = field(default_factory=list)
    total: int = 0

    def add(self, muestras: np.ndarray) -> np.ndarray | None:
        self.partes.append(muestras)
        self.total += len(muestras)
        if self.total < self.objetivo:
            return None
        bloque = np.concatenate(self.partes)
        self.partes.clear()
        self.total = 0
        return bloque


class CallPipeline:
    """Consume tramas de audio y publica la transcripción como eventos."""

    def __init__(
        self,
        *,
        call_id: str,
        customer_id: str,
        agent_id: str,
        asr: StreamingASR,
        bus: EventBus,
        ingress: str,
        scenario_id: str | None = None,
    ) -> None:
        self._call_id = call_id
        self._customer_id = customer_id
        self._agent_id = agent_id
        self._asr = asr
        self._bus = bus
        self._ingress = ingress
        self._scenario_id = scenario_id

        self._seq = 0
        self._inicio = 0.0
        objetivo = int(asr.sample_rate * BLOQUE_MS / 1000)
        self._acum = {s: _Acumulador(objetivo) for s in (Speaker.CUSTOMER, Speaker.AGENT)}

    def _siguiente_seq(self) -> int:
        self._seq += 1
        return self._seq

    async def start(self, room: str) -> None:
        self._inicio = time.perf_counter()
        for speaker in (Speaker.CUSTOMER, Speaker.AGENT):
            self._asr.open(self._call_id, speaker)
        await self._bus.publish(
            CallStarted(
                call_id=self._call_id,
                seq=self._siguiente_seq(),
                customer_id=self._customer_id,
                agent_id=self._agent_id,
                room=room,
                ingress=self._ingress,
                sample_rate=self._asr.sample_rate,
            )
        )

    async def feed(self, frame: AudioFrame) -> None:
        bloque = self._acum[frame.speaker].add(pcm16_a_float32(frame.pcm16))
        if bloque is None:
            return

        for hip in self._asr.accept(self._call_id, frame.speaker, bloque):
            await self._emitir(hip, frame.ts_ms)

    async def stop(self, reason: str = "normal") -> None:
        for speaker in (Speaker.CUSTOMER, Speaker.AGENT):
            for hip in self._asr.close(self._call_id, speaker):
                await self._emitir(hip, None)

        await self._bus.publish(
            CallEnded(
                call_id=self._call_id,
                seq=self._siguiente_seq(),
                duration_ms=int((time.perf_counter() - self._inicio) * 1000),
                reason=reason,
            )
        )

    async def _emitir(self, hip, ts_ms: int | None) -> None:
        if hip.is_final:
            await self._bus.publish(
                AsrFinal(
                    call_id=self._call_id,
                    seq=self._siguiente_seq(),
                    speaker=hip.speaker,
                    turn_id=hip.turn_id,
                    text=hip.text,
                    started_at_ms=hip.started_at_ms,
                    ended_at_ms=hip.ended_at_ms or hip.started_at_ms,
                )
            )
            # El fin de turno va como evento propio y no como una bandera del
            # texto: es lo que disparará la sugerencia del copiloto, y el
            # orquestador no debería tener que inspeccionar transcripciones
            # para enterarse de que alguien dejó de hablar.
            await self._bus.publish(
                TurnEnded(
                    call_id=self._call_id,
                    seq=self._siguiente_seq(),
                    speaker=hip.speaker,
                    turn_id=hip.turn_id,
                    predicted=False,
                )
            )
        else:
            await self._bus.publish(
                AsrPartial(
                    call_id=self._call_id,
                    seq=self._siguiente_seq(),
                    speaker=hip.speaker,
                    turn_id=hip.turn_id,
                    text=hip.text,
                    started_at_ms=hip.started_at_ms,
                )
            )
