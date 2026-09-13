"""Descriptores prosódicos de una ventana de audio.

Todo lo de aquí es procesado de señal y estadística: energía, cadencia, tono.
No hay modelo entrenado y es deliberado. Estas señales son independientes del
idioma —no hace falta un modelo entrenado en español para saber que alguien
subió la voz—, se calculan en microsegundos y, sobre todo, son explicables: en
un banco poder decir "la barra subió porque habla un 40% más fuerte y un 25%
más rápido que hace un minuto" vale más que un número salido de una red que
nadie puede auditar.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Por debajo de esto una ventana se considera silencio y no aporta.
#
# Medir "energía" sobre silencio arrastra la referencia del hablante hacia
# abajo y hace que cualquier palabra posterior parezca un grito.
UMBRAL_VOZ_RMS = 0.004

# Rango de frecuencia fundamental que se busca. Cubre voz grave masculina y
# aguda femenina sin perseguir armónicos fuera de la voz humana.
F0_MIN_HZ = 70
F0_MAX_HZ = 400


@dataclass(slots=True, frozen=True)
class Descriptores:
    """Lo medible de una ventana. Crudo, sin interpretar."""

    rms: float
    """Energía cuadrática media. Proxy de volumen."""

    rms_pico: float
    """Máximo absoluto. Separa un grito puntual de hablar alto sostenido."""

    tasa_cruces_cero: float
    """Cruces por cero. Sube con la aspereza y las consonantes fricativas."""

    f0_hz: float
    """Frecuencia fundamental estimada. 0 si la ventana no es sonora."""

    proporcion_voz: float
    """Fracción de la ventana con voz. Proxy inverso de las pausas."""

    @property
    def hay_voz(self) -> bool:
        return self.rms >= UMBRAL_VOZ_RMS


def _estimar_f0(muestras: np.ndarray, sample_rate: int) -> float:
    """F0 por autocorrelación normalizada.

    Se usa autocorrelación y no un método espectral porque sobre ventanas
    cortas y voz telefónica —donde el primer armónico puede haberse perdido con
    el filtrado a 8 kHz— es más estable. No pretende ser un extractor de tono
    de calidad fonética: basta con detectar que alguien tensa la voz.
    """
    if len(muestras) < sample_rate // F0_MIN_HZ:
        return 0.0

    señal = muestras - muestras.mean()
    energia = float(np.dot(señal, señal))
    if energia <= 0:
        return 0.0

    corr = np.correlate(señal, señal, mode="full")[len(señal) - 1 :]
    lag_min = int(sample_rate / F0_MAX_HZ)
    lag_max = min(int(sample_rate / F0_MIN_HZ), len(corr) - 1)
    if lag_max <= lag_min:
        return 0.0

    ventana = corr[lag_min:lag_max]
    mejor = int(np.argmax(ventana)) + lag_min
    # Correlación normalizada baja = ventana no sonora (ruido, fricativa,
    # silencio). Reportar un tono ahí sería inventarse una señal.
    if corr[mejor] / energia < 0.3:
        return 0.0
    return sample_rate / mejor


def extraer(muestras: np.ndarray, sample_rate: int, *, sub_ventana_ms: int = 20) -> Descriptores:
    """Calcula los descriptores de una ventana de audio."""
    if muestras.size == 0:
        return Descriptores(0.0, 0.0, 0.0, 0.0, 0.0)

    rms = float(np.sqrt(np.mean(muestras**2)))
    pico = float(np.max(np.abs(muestras)))
    cruces = float(np.mean(np.abs(np.diff(np.signbit(muestras))))) if muestras.size > 1 else 0.0

    paso = max(1, int(sample_rate * sub_ventana_ms / 1000))
    sub = [muestras[i : i + paso] for i in range(0, len(muestras), paso)]
    con_voz = sum(1 for s in sub if np.sqrt(np.mean(s**2)) >= UMBRAL_VOZ_RMS)
    proporcion = con_voz / len(sub) if sub else 0.0

    f0 = _estimar_f0(muestras, sample_rate) if rms >= UMBRAL_VOZ_RMS else 0.0

    return Descriptores(
        rms=rms,
        rms_pico=pico,
        tasa_cruces_cero=cruces,
        f0_hz=f0,
        proporcion_voz=proporcion,
    )
