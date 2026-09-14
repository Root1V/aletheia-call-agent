"""Bus de eventos de la llamada.

Un stream de Redis por llamada. Redis Streams y no pub/sub porque el stream
CONSERVA lo publicado: un ejecutivo que recarga el portal a mitad de llamada
recupera la transcripción desde el principio en lugar de encontrarse un panel
en blanco. Con pub/sub, lo emitido antes de suscribirse simplemente no existe.

Ese mismo registro es lo que permite reproducir una llamada completa para
depurarla o para correr evaluaciones deterministas sobre tráfico real.
"""

from .bus import CLAVE_DIRECTORIO, EventBus, clave_de_contexto, clave_de_seq, clave_de_stream

__all__ = [
    "CLAVE_DIRECTORIO",
    "EventBus",
    "clave_de_contexto",
    "clave_de_seq",
    "clave_de_stream",
]
