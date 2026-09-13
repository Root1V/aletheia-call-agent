"""Motor de estado emocional del cliente.

ALCANCE, y conviene ser explícito porque es fácil vender esto de más: lo que
hay aquí mide la señal PROSÓDICA Y CONVERSACIONAL —cuánta energía, qué tono,
a qué ritmo, cuánto interrumpe— comparada con la línea base del propio
hablante. Con eso se puede sostener honestamente la ACTIVACIÓN, y de ahí
derivar frustración y urgencia.

Lo que NO se mide todavía:

- **Valencia** (si lo que siente es agradable o desagradable). La prosodia sola
  no la distingue: alegría y enfado comparten energía alta, tono alto y ritmo
  rápido. Hace falta el modelo acústico o el texto.
- **Satisfacción** y **confusión**, por lo mismo.

Esas dimensiones se devuelven ausentes, no en cero. Un cero se lee como
"neutral" y "no lo sé" no es "neutral": si el panel las pintara a la mitad,
el ejecutivo creería que el sistema afirma algo que no ha medido.

LIMITACIÓN QUE HAY QUE TENER PRESENTE AL LEER LAS BARRAS. Como la referencia es
la propia voz del cliente al principio de la llamada, esto mide CAMBIO, no
estado absoluto. Un cliente que entra gritando y sigue gritando establece su
grito como referencia y se lee como neutro; lo que el motor detecta bien es que
se altere, o que se calme.

Para la detección de escalamiento —que es el uso que importa— eso basta y
sobra: lo accionable es el cliente que se está calentando, no el que ya llegó
caliente y el ejecutivo tiene delante. Para afirmar "este cliente está enfadado"
en términos absolutos harían falta o un modelo acústico entrenado, o una
referencia poblacional construida sobre muchas llamadas. Ninguna de las dos
está todavía.

Sólo se procesa el audio del CLIENTE. La restricción vive en el tipo
`EmotionFrame`, no aquí.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from cea_contracts import EmotionFrame, EmotionLabel

from .baseline import LineaBase
from .features import Descriptores, extraer

# Cadencia de salida. Dos por segundo es suficiente para que una barra se vea
# viva y bastante poco como para no inundar el bus ni el navegador.
HOP_MS = 500
VENTANA_MS = 2500

# Suavizado exponencial de la salida.
#
# Sin él la barra tiembla con cada sílaba y se vuelve ilegible; con demasiado,
# llega tarde al enfado. 0.35 sobre muestras a 2 Hz da una constante de tiempo
# de algo más de un segundo.
ALFA_SUAVIZADO = 0.35

# Por debajo de esta confianza la UI pinta la banda en gris en lugar de dar un
# valor. Inventar una emoción con señal pobre es peor que no decir nada.
CONFIANZA_MINIMA = 0.35


# Calibración del mapeo de z-score a barra.
#
# Los valores salen de medir, no de estimar. Sobre habla de referencia y habla
# claramente más energética y rápida, el z combinado se reparte así:
#
#   habla normal ..................... −0.3 a 1.2
#   claramente más activado .......... ~2.6
#   muy por encima de su propia voz .. ~6.6
#
# La primera versión usaba centro 1.5 y pendiente 1.2, y ya saturaba en 0.98
# con el caso intermedio: la barra sólo sabía decir 0.05 o 0.95, un indicador
# binario disfrazado de medidor. Con el centro en 2.6 el punto medio coincide
# con "claramente activado", y la escala de 4.5 deja el extremo cerca de 0.9 en
# lugar de clavarlo en 1.0, para que siga habiendo margen por encima.
CENTRO_SIGMOIDE = 2.6
PENDIENTE_SIGMOIDE = 0.55
ESCALA_ACTIVACION = 4.5

# Tope de cada z individual antes de combinarlos.
#
# Un recorte de señal o un golpe en el auricular producen z enormes en energía
# que, sin este límite, aplastan la contribución del tono y del ritmo y dejan
# la barra clavada arriba por un artefacto.
Z_MAXIMO = 8.0


def _recortar(z: float) -> float:
    return max(-Z_MAXIMO, min(Z_MAXIMO, z))


def _sigmoide(
    x: float, centro: float = CENTRO_SIGMOIDE, pendiente: float = PENDIENTE_SIGMOIDE
) -> float:
    """Convierte un z-score en una proporción de 0 a 1."""
    return 1.0 / (1.0 + math.exp(-pendiente * (x - centro)))


@dataclass(slots=True)
class SeñalesConversacionales:
    """Lo que se sabe del diálogo, no de la señal de audio.

    Se alimenta desde fuera: quién interrumpió a quién y cuánto habla cada uno
    lo sabe el pipeline, que ve ambos canales.
    """

    interrupciones: int = 0
    turnos_del_cliente: int = 0
    palabras_por_minuto: float = 0.0

    @property
    def tasa_de_interrupcion(self) -> float:
        if self.turnos_del_cliente == 0:
            return 0.0
        return self.interrupciones / self.turnos_del_cliente


@dataclass(slots=True)
class _Estado:
    linea: LineaBase = field(default_factory=LineaBase)
    buffer: list[np.ndarray] = field(default_factory=list)
    muestras_en_buffer: int = 0
    # Contador independiente del búfer.
    #
    # El búfer conserva 2.5 s de contexto, así que su tamaño se queda fijo en
    # el máximo y deja de servir para decidir cuándo toca emitir: comparando
    # contra él, el motor emitía en CADA bloque de entrada —diez por segundo en
    # vez de dos— e inundaba el bus con fotogramas idénticos.
    muestras_desde_emision: int = 0
    suavizado: dict[EmotionLabel, float] = field(default_factory=dict)
    activacion_suavizada: float = 0.0
    posicion_ms: int = 0


class MotorDeEmocion:
    """Convierte audio del cliente en un estado emocional calibrado."""

    def __init__(self, sample_rate: int = 16000) -> None:
        self._sr = sample_rate
        self._ventana = int(sample_rate * VENTANA_MS / 1000)
        self._hop = int(sample_rate * HOP_MS / 1000)
        self._estados: dict[str, _Estado] = {}

    def abrir(self, call_id: str) -> None:
        self._estados[call_id] = _Estado()

    def cerrar(self, call_id: str) -> None:
        self._estados.pop(call_id, None)

    def procesar(
        self,
        call_id: str,
        muestras: np.ndarray,
        *,
        conversacional: SeñalesConversacionales | None = None,
    ) -> EmotionFrame | None:
        """Acumula audio y devuelve un fotograma cada `HOP_MS`."""
        estado = self._estados.get(call_id)
        if estado is None:
            self.abrir(call_id)
            estado = self._estados[call_id]

        estado.buffer.append(muestras)
        estado.muestras_en_buffer += len(muestras)
        estado.muestras_desde_emision += len(muestras)
        estado.posicion_ms += int(len(muestras) / self._sr * 1000)

        if estado.muestras_desde_emision < self._hop:
            return None
        estado.muestras_desde_emision = 0

        audio = np.concatenate(estado.buffer)
        # Se conserva una ventana de contexto; el resto se descarta. La emoción
        # se lee sobre 2.5 s, no sobre los 500 ms del último salto.
        if len(audio) > self._ventana:
            audio = audio[-self._ventana :]
        estado.buffer = [audio]
        estado.muestras_en_buffer = len(audio)

        d = extraer(audio, self._sr)
        estado.linea.observar(d)
        return self._evaluar(call_id, estado, d, conversacional or SeñalesConversacionales())

    # ── cálculo ──────────────────────────────────────────────────────────────

    def _evaluar(
        self,
        call_id: str,
        estado: _Estado,
        d: Descriptores,
        conv: SeñalesConversacionales,
    ) -> EmotionFrame:
        linea = estado.linea
        confianza = self._confianza(d, linea)

        z_energia = _recortar(linea.energia.z(d.rms)) if linea.lista else 0.0
        z_tono = _recortar(linea.tono.z(d.f0_hz)) if linea.lista and d.f0_hz > 0 else 0.0
        z_ritmo = _recortar(linea.ritmo.z(d.proporcion_voz)) if linea.lista else 0.0

        # Activación: lo que la prosodia sí sostiene. Energía y tono pesan más
        # que el ritmo porque son los que mejor separan hablar de alzar la voz.
        combinado = 0.45 * z_energia + 0.35 * z_tono + 0.20 * z_ritmo
        activacion_cruda = float(np.tanh(combinado / ESCALA_ACTIVACION))
        estado.activacion_suavizada = _ema(estado.activacion_suavizada, activacion_cruda)

        # Las interrupciones pesan alto porque son una señal conversacional
        # directa: quien interrumpe intenta recuperar el control de la
        # conversación, y eso no se deduce de la prosodia.
        frustracion = _sigmoide(0.5 * z_energia + 0.3 * z_tono + 3.0 * conv.tasa_de_interrupcion)
        urgencia = _sigmoide(0.55 * z_ritmo + 0.35 * z_energia)

        crudos = {
            EmotionLabel.FRUSTRACION: frustracion,
            EmotionLabel.URGENCIA: urgencia,
        }
        for etiqueta, valor in crudos.items():
            estado.suavizado[etiqueta] = _ema(estado.suavizado.get(etiqueta, 0.0), valor)

        return EmotionFrame(
            call_id=call_id,
            ts_ms=estado.posicion_ms,
            # Sólo las dimensiones que hay evidencia para afirmar. Las demás no
            # se envían: la UI las muestra como pendientes en lugar de pintar
            # un cero que se leería como "neutral".
            scores={k: round(v, 3) for k, v in estado.suavizado.items()},
            valence=None,
            arousal=round(estado.activacion_suavizada, 3),
            confidence=round(confianza, 3),
            window_ms=VENTANA_MS,
            contributions={
                "prosodica": 0.75,
                "conversacional": 0.25 if conv.turnos_del_cliente else 0.0,
                # El hueco declarado: cuando entre un modelo acústico validado
                # para español, aquí aparecerá su peso y la fusión cambiará sin
                # que la UI se entere.
                "acustica_modelo": 0.0,
            },
        )

    def _confianza(self, d: Descriptores, linea: LineaBase) -> float:
        """Cuánto crédito merece este fotograma.

        Baja con el silencio —no se puede leer la emoción de quien no habla— y
        con una referencia todavía inmadura.
        """
        if not d.hay_voz:
            return 0.0
        calidad_señal = min(1.0, d.proporcion_voz * 1.6)
        return round(calidad_señal * linea.madurez, 3)


def _ema(anterior: float, nuevo: float, alfa: float = ALFA_SUAVIZADO) -> float:
    return (1 - alfa) * anterior + alfa * nuevo
