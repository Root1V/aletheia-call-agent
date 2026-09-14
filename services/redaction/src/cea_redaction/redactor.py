"""Redacción de datos sensibles en el texto de una llamada."""

from __future__ import annotations

from dataclasses import dataclass, field

from cea_contracts import PIIKind

from .detectores import Hallazgo, detectar_cvv, detectar_en_cadena
from .numeros import extraer_cadenas

# Cómo se tacha cada tipo.
#
# Las etiquetas se dejan legibles en vez de sustituir por asteriscos: el
# ejecutivo tiene que poder seguir el hilo de la conversación. "El cliente
# dictó [DNI]" se entiende; "el cliente dictó ********" parece un error de la
# transcripción.
ETIQUETAS: dict[PIIKind, str] = {
    PIIKind.DNI: "[DNI]",
    PIIKind.RUC: "[RUC]",
    PIIKind.CCI: "[CCI]",
    PIIKind.NUMERO_TARJETA: "[N.º TARJETA]",
    PIIKind.CVV: "[CÓD. SEGURIDAD]",
    PIIKind.FECHA_VENCIMIENTO: "[VENCIMIENTO]",
    PIIKind.NUMERO_CUENTA: "[N.º CUENTA]",
    PIIKind.TELEFONO: "[TELÉFONO]",
    PIIKind.EMAIL: "[CORREO]",
    PIIKind.DIRECCION: "[DIRECCIÓN]",
    PIIKind.NOMBRE: "[NOMBRE]",
}


@dataclass(slots=True)
class Redaccion:
    """Resultado de redactar un texto."""

    texto: str
    """El texto ya tachado. Es el ÚNICO que debe salir de aquí."""

    hallazgos: tuple[Hallazgo, ...] = ()
    tipos: tuple[PIIKind, ...] = field(default=())

    @property
    def hubo_cambios(self) -> bool:
        return bool(self.hallazgos)


def _sin_solapar(hallazgos: list[Hallazgo]) -> list[Hallazgo]:
    """Descarta los hallazgos contenidos en otro más largo.

    Un PAN de dieciséis cifras contiene tiradas que también parecen un DNI.
    Tacharlos por separado dejaría marcas anidadas y un texto ilegible.
    """
    ordenados = sorted(hallazgos, key=lambda h: (h.inicio, -(h.fin - h.inicio)))
    salida: list[Hallazgo] = []
    for h in ordenados:
        if salida and h.inicio < salida[-1].fin:
            continue
        salida.append(h)
    return salida


def redactar(texto: str) -> Redaccion:
    """Tacha todo dato sensible del texto.

    Se aplica ANTES de persistir y ANTES de construir cualquier prompt. El
    orden no es un detalle: una vez que el número está en la base de datos o en
    el historial de un proveedor de modelos, redactarlo después no lo
    des-publica.
    """
    if not texto.strip():
        return Redaccion(texto=texto)

    cadenas = extraer_cadenas(texto)
    hallazgos: list[Hallazgo] = []
    for cadena in cadenas:
        hallazgos.extend(detectar_en_cadena(cadena, texto))
    hallazgos.extend(detectar_cvv(texto, cadenas))

    hallazgos = _sin_solapar(hallazgos)
    if not hallazgos:
        return Redaccion(texto=texto)

    # Se reemplaza de atrás hacia adelante para que los índices de los
    # hallazgos anteriores sigan siendo válidos.
    salida = texto
    for h in sorted(hallazgos, key=lambda h: h.inicio, reverse=True):
        salida = salida[: h.inicio] + ETIQUETAS[h.kind] + salida[h.fin :]

    return Redaccion(
        texto=salida,
        hallazgos=tuple(hallazgos),
        tipos=tuple(dict.fromkeys(h.kind for h in hallazgos)),
    )
