"""Reconocedor de streaming sobre sherpa-onnx.

Transducer Zipformer corriendo en CPU con ONNX Runtime. En esta máquina
alcanza RTF ~0.016 sobre español, es decir unas sesenta veces más rápido que el
tiempo real, lo que deja margen de sobra para varias llamadas por proceso.
"""

from __future__ import annotations

import logging
import re
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import sherpa_onnx
from cea_contracts import Speaker

from .base import Hypothesis

log = logging.getLogger("cea.asr")

# Silencio que se inyecta al cerrar un turno, antes de leer el resultado final.
#
# El Zipformer decodifica con lookahead: mientras no llega audio posterior, se
# guarda las últimas palabras. Sin esta cola, el final de cada turno se pierde
# de forma sistemática y silenciosa —la transcripción se ve razonable, sólo que
# le faltan las dos o tres últimas palabras—.
#
# La cantidad necesaria NO es constante: depende del estado del decodificador
# al terminar el turno. Medido sobre este modelo, un turno largo se completa
# con 800 ms mientras que uno corto de 2.85 s todavía pierde la última palabra
# con 1000 ms y sólo sale entero a partir de 1500 ms. Por eso el valor se fija
# holgado en lugar de ajustarlo al mínimo que funcionaba en el primer caso
# probado.
#
# Que esta cola supere `silencio_con_texto_s` y dispare un fin de turno interno
# es inofensivo: un fin de turno no borra el resultado, sólo lo haría `reset()`,
# y en el cierre nunca se llama. El coste es despreciable —1.5 s de silencio a
# RTF 0.02 son unos 30 ms de cómputo— y ocurre cuando el turno ya terminó, así
# que no entra en la latencia que el ejecutivo percibe.
COLA_DE_SILENCIO_MS = 1500


_TIENE_LETRAS = re.compile(r"[^\W_]", re.UNICODE)


def _es_solo_puntuacion(texto: str) -> bool:
    """Si el texto no contiene ninguna letra ni dígito.

    Tras cerrar un turno, el modelo emite a veces el signo de puntuación final
    como un turno nuevo: queda un "." suelto con su propio turn_id. En la UI
    eso son burbujas vacías con un punto dentro, y aguas abajo son turnos sin
    contenido que dispararían una sugerencia del copiloto sobre nada.
    """
    return not _TIENE_LETRAS.search(texto)


@dataclass(slots=True)
class _EstadoDeHablante:
    """Estado de decodificación de un hablante dentro de una llamada."""

    stream: sherpa_onnx.OnlineStream
    turn_id: str
    texto_emitido: str = ""
    muestras_totales: int = 0
    inicio_turno_ms: int = 0
    _sr: int = field(default=16000, repr=False)

    @property
    def posicion_ms(self) -> int:
        return int(self.muestras_totales / self._sr * 1000)


class SherpaStreamingASR:
    """Implementación de `StreamingASR` con un transducer Zipformer."""

    def __init__(
        self,
        model_dir: Path | str,
        *,
        sample_rate: int = 16000,
        num_threads: int = 2,
        # Reglas de fin de turno de sherpa-onnx.
        #
        # Los nombres de la librería se prestan a un error caro:
        # `rule3_min_utterance_length` NO es "duración mínima para que un turno
        # cuente". Es "forzar el corte cuando el turno supera esta duración,
        # haya o no silencio". Ponerlo bajo trocea las palabras por la mitad
        # ("aplica ción", "oche nta") y dispara el WER sin que nada falle de
        # forma visible. Aquí actúa sólo como tope de seguridad para que un
        # monólogo no crezca sin límite.
        silencio_sin_texto_s: float = 2.0,
        silencio_con_texto_s: float = 0.9,
        duracion_maxima_turno_s: float = 18.0,
    ) -> None:
        d = Path(model_dir)
        faltan = [
            f
            for f in ("encoder.onnx", "decoder.onnx", "joiner.onnx", "tokens.txt")
            if not (d / f).exists()
        ]
        if faltan:
            raise FileNotFoundError(
                f"Faltan archivos del modelo en {d}: {', '.join(faltan)}. "
                "Ejecutar `make models` para descargarlo."
            )

        self._sample_rate = sample_rate
        self._recognizer = sherpa_onnx.OnlineRecognizer.from_transducer(
            tokens=str(d / "tokens.txt"),
            encoder=str(d / "encoder.onnx"),
            decoder=str(d / "decoder.onnx"),
            joiner=str(d / "joiner.onnx"),
            num_threads=num_threads,
            sample_rate=sample_rate,
            feature_dim=80,
            enable_endpoint_detection=True,
            # rule1: silencio necesario cuando aún no se decodificó nada.
            rule1_min_trailing_silence=silencio_sin_texto_s,
            # rule2: silencio tras haber decodificado texto. Es la que marca el
            # ritmo conversacional: 0.9 s corta entre frases sin partir una.
            rule2_min_trailing_silence=silencio_con_texto_s,
            # rule3: tope de seguridad, no un mínimo.
            rule3_min_utterance_length=duracion_maxima_turno_s,
        )
        self._model_name = d.name
        self._estados: dict[tuple[str, Speaker], _EstadoDeHablante] = {}

    @property
    def name(self) -> str:
        return f"sherpa:{self._model_name}"

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    # ── ciclo de vida ────────────────────────────────────────────────────────

    def open(self, call_id: str, speaker: Speaker) -> None:
        self._estados[(call_id, speaker)] = _EstadoDeHablante(
            stream=self._recognizer.create_stream(),
            turn_id=uuid.uuid4().hex[:12],
            _sr=self._sample_rate,
        )

    def accept(self, call_id: str, speaker: Speaker, samples: np.ndarray) -> Iterator[Hypothesis]:
        """Consume audio y emite hipótesis sólo cuando el texto cambia.

        Reemitir la misma hipótesis en cada trozo inundaría el bus de eventos y
        haría repintar la UI cincuenta veces por segundo sin que nada cambie en
        pantalla.
        """
        estado = self._estados.get((call_id, speaker))
        if estado is None:
            self.open(call_id, speaker)
            estado = self._estados[(call_id, speaker)]

        if samples.dtype != np.float32:
            samples = samples.astype(np.float32)

        estado.stream.accept_waveform(self._sample_rate, samples)
        estado.muestras_totales += len(samples)
        while self._recognizer.is_ready(estado.stream):
            self._recognizer.decode_stream(estado.stream)

        texto = self._recognizer.get_result(estado.stream).strip()

        # Fin de turno detectado por el propio reconocedor (silencio sostenido).
        if self._recognizer.is_endpoint(estado.stream):
            if texto and not _es_solo_puntuacion(texto):
                yield Hypothesis(
                    speaker=speaker,
                    turn_id=estado.turn_id,
                    text=texto,
                    is_final=True,
                    started_at_ms=estado.inicio_turno_ms,
                    ended_at_ms=estado.posicion_ms,
                )
            # Un turno nuevo empieza con identidad nueva: la UI lo usa para
            # decidir si sustituye la burbuja anterior o abre otra.
            self._recognizer.reset(estado.stream)
            estado.turn_id = uuid.uuid4().hex[:12]
            estado.texto_emitido = ""
            estado.inicio_turno_ms = estado.posicion_ms
            return

        if texto and texto != estado.texto_emitido and not _es_solo_puntuacion(texto):
            estado.texto_emitido = texto
            yield Hypothesis(
                speaker=speaker,
                turn_id=estado.turn_id,
                text=texto,
                is_final=False,
                started_at_ms=estado.inicio_turno_ms,
            )

    def close(self, call_id: str, speaker: Speaker) -> Iterator[Hypothesis]:
        estado = self._estados.pop((call_id, speaker), None)
        if estado is None:
            return

        # Cola de silencio para vaciar el lookahead. Sin esto se pierden
        # sistemáticamente las últimas palabras del turno.
        cola = np.zeros(int(self._sample_rate * COLA_DE_SILENCIO_MS / 1000), dtype=np.float32)
        estado.stream.accept_waveform(self._sample_rate, cola)
        while self._recognizer.is_ready(estado.stream):
            self._recognizer.decode_stream(estado.stream)

        estado.stream.input_finished()
        while self._recognizer.is_ready(estado.stream):
            self._recognizer.decode_stream(estado.stream)

        texto = self._recognizer.get_result(estado.stream).strip()
        if texto and not _es_solo_puntuacion(texto):
            yield Hypothesis(
                speaker=speaker,
                turn_id=estado.turn_id,
                text=texto,
                is_final=True,
                started_at_ms=estado.inicio_turno_ms,
                ended_at_ms=estado.posicion_ms,
            )

    def close_all(self, call_id: str) -> Iterator[Hypothesis]:
        for speaker in (Speaker.CUSTOMER, Speaker.AGENT):
            yield from self.close(call_id, speaker)
