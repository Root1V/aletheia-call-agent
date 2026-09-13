"""Línea base de un hablante dentro de una llamada.

Es la pieza que hace que las señales prosódicas signifiquen algo. La energía
absoluta no dice nada: depende de la ganancia de la línea, del micrófono, de lo
cerca que esté el auricular. Una persona de voz fuerte mediría siempre "muy
activada" y una de voz baja no llegaría nunca al umbral.

Lo que sí significa algo es la desviación respecto a cómo hablaba ESA persona
al principio de ESTA llamada. Por eso la referencia se aprende en caliente.

SOBRE POR QUÉ NO ES UNA MEDIA MÓVIL. La primera versión usaba media y varianza
exponenciales actualizadas con cada ventana, y medía exactamente al revés: daba
activación 0.62 con el cliente hablando tranquilo y 0.10 con el cliente
gritando. Dos motivos, ambos inherentes a esa elección:

1. La varianza exponencial se dispara con el propio cambio que se quiere
   detectar. Al llegar el habla alterada, el salto engorda el denominador del
   z-score y el resultado se encoge: el grito se enmascara a sí mismo.
2. La media persigue al hablante. Un cliente que lleva dos minutos gritando
   "normaliza" su grito y la barra vuelve a cero justo cuando más importa.

Ahora la referencia se estima con mediana y desviación absoluta mediana sobre
las primeras ventanas con voz, y luego se CONGELA. Sólo deriva con ventanas que
ya caen dentro de lo normal, de modo que sigue el cansancio de la voz a lo
largo de la llamada sin perseguir el enfado.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .features import Descriptores

# Ventanas con voz que se recogen antes de fijar la referencia.
#
# A 2 Hz son unos seis segundos de habla. Con menos, la referencia es la
# primera frase y cualquier cosa posterior parece una desviación enorme: el
# panel se dispararía en cuanto alguien saluda con energía.
VENTANAS_DE_CALENTAMIENTO = 12

# Desviaciones dentro de las cuales una ventana se considera "hablar normal" y
# puede seguir alimentando la referencia. Fuera de eso se observa pero no se
# incorpora: es justamente lo que se quiere medir.
UMBRAL_DE_DERIVA = 1.5

# Peso de una ventana normal sobre la referencia ya fijada. Muy bajo: permite
# seguir la deriva natural de la voz sin borrar el punto de partida.
ALFA_DERIVA = 0.01

# Suelo de la dispersión.
#
# Un hablante muy uniforme tiene una MAD diminuta, y sin este suelo cualquier
# inflexión trivial se convertiría en un z-score enorme.
DISPERSION_MINIMA = {"energia": 0.004, "tono": 6.0, "ritmo": 0.05}

# La MAD se escala para ser comparable a una desviación típica bajo normalidad.
FACTOR_MAD = 1.4826


def _mediana(xs: list[float]) -> float:
    if not xs:
        return 0.0
    ordenados = sorted(xs)
    n = len(ordenados)
    medio = n // 2
    if n % 2:
        return ordenados[medio]
    return (ordenados[medio - 1] + ordenados[medio]) / 2


def _mad(xs: list[float], centro: float) -> float:
    """Desviación absoluta mediana.

    Robusta frente a valores extremos: una sola palabra gritada durante el
    calentamiento no ensancha la referencia como sí haría la desviación típica.
    """
    if not xs:
        return 0.0
    return _mediana([abs(x - centro) for x in xs]) * FACTOR_MAD


@dataclass(slots=True)
class _Dimension:
    """Referencia de una magnitud: dónde está el centro y cuánto varía."""

    nombre: str
    muestras: list[float] = field(default_factory=list)
    centro: float = 0.0
    dispersion: float = 0.0
    fijada: bool = False

    def recoger(self, x: float) -> None:
        if self.fijada:
            # Ya hay referencia: sólo derivan las ventanas normales.
            if abs(self.z(x)) <= UMBRAL_DE_DERIVA:
                self.centro = (1 - ALFA_DERIVA) * self.centro + ALFA_DERIVA * x
            return
        self.muestras.append(x)

    def fijar(self) -> None:
        if self.fijada or not self.muestras:
            return
        self.centro = _mediana(self.muestras)
        self.dispersion = max(
            _mad(self.muestras, self.centro), DISPERSION_MINIMA.get(self.nombre, 1e-3)
        )
        self.fijada = True
        self.muestras = []

    def z(self, x: float) -> float:
        if not self.fijada:
            return 0.0
        return (x - self.centro) / self.dispersion


@dataclass(slots=True)
class LineaBase:
    """Cómo habla este hablante cuando no pasa nada."""

    energia: _Dimension = field(default_factory=lambda: _Dimension("energia"))
    tono: _Dimension = field(default_factory=lambda: _Dimension("tono"))
    ritmo: _Dimension = field(default_factory=lambda: _Dimension("ritmo"))
    ventanas_con_voz: int = 0

    @property
    def lista(self) -> bool:
        return self.energia.fijada

    @property
    def madurez(self) -> float:
        """De 0 a 1: cuánto se puede confiar en la referencia todavía."""
        return min(1.0, self.ventanas_con_voz / VENTANAS_DE_CALENTAMIENTO)

    def observar(self, d: Descriptores) -> None:
        """Incorpora una ventana. El silencio no cuenta.

        Alimentar la referencia con silencio la arrastra hacia abajo y hace que
        la siguiente palabra, por normal que sea, parezca un grito.
        """
        if not d.hay_voz:
            return
        self.ventanas_con_voz += 1
        self.energia.recoger(d.rms)
        self.ritmo.recoger(d.proporcion_voz)
        if d.f0_hz > 0:
            self.tono.recoger(d.f0_hz)

        if self.ventanas_con_voz == VENTANAS_DE_CALENTAMIENTO:
            for dim in (self.energia, self.tono, self.ritmo):
                dim.fijar()
