"""Registro de modelos de voz.

Los pesos NO se versionan en el repositorio: se descargan en `models/` durante
la instalación. No es sólo por tamaño. Cada modelo trae su propia licencia,
distinta de la del proyecto, y vendorizarlo dentro de un repositorio Apache-2.0
mezcla obligaciones que conviene mantener separadas. Descargándolo, el código
sigue siendo Apache-2.0 y el modelo conserva la suya, que este registro muestra
de forma explícita al instalar.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class ModeloDeVoz:
    clave: str
    nombre: str
    url: str
    directorio: str
    licencia: str
    idiomas: tuple[str, ...]
    streaming: bool
    tamano_mb: int
    nota: str = ""


MODELOS: dict[str, ModeloDeVoz] = {
    "asr-es-streaming": ModeloDeVoz(
        clave="asr-es-streaming",
        nombre="Kroko Streaming Zipformer (español)",
        url=(
            "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
            "sherpa-onnx-streaming-zipformer-es-kroko-2025-08-06.tar.bz2"
        ),
        directorio="sherpa-onnx-streaming-zipformer-es-kroko-2025-08-06",
        licencia="CC-BY-SA-4.0",
        idiomas=("es",),
        streaming=True,
        tamano_mb=124,
        nota=(
            "ATENCIÓN: es el ÚNICO modelo de streaming en español del catálogo de "
            "sherpa-onnx; todo lo demás con streaming es inglés, chino, ruso, persa, "
            "francés, alemán, coreano o bengalí. Su licencia CC-BY-SA obliga a citar "
            "la fuente y a compartir bajo la misma licencia cualquier obra derivada "
            "de los PESOS. Usarlo para transcribir no convierte al software ni a las "
            "transcripciones en obra derivada, pero conviene que el área legal lo "
            "confirme antes del piloto. La alternativa limpia es 'asr-es-offline'."
        ),
    ),
    "asr-es-offline": ModeloDeVoz(
        clave="asr-es-offline",
        nombre="NVIDIA NeMo FastConformer Transducer (español)",
        url=(
            "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
            "sherpa-onnx-nemo-fast-conformer-transducer-es-1424-int8.tar.bz2"
        ),
        directorio="sherpa-onnx-nemo-fast-conformer-transducer-es-1424-int8",
        licencia="CC-BY-4.0",
        idiomas=("es",),
        streaming=False,
        tamano_mb=107,
        nota=(
            "Licencia limpia para uso comercial con atribución. No hace streaming: "
            "transcribe por segmentos, así que el texto aparece al cerrar cada turno "
            "en vez de mientras la persona habla. Es la vía precisa de la "
            "arquitectura de dos velocidades y el reemplazo si CC-BY-SA se descarta."
        ),
    ),
}


def resumen_de_licencias() -> str:
    lineas = ["Modelos de voz y sus licencias:", ""]
    for m in MODELOS.values():
        modo = "streaming" if m.streaming else "por segmentos"
        lineas.append(f"  {m.clave}")
        lineas.append(f"    {m.nombre}")
        lineas.append(f"    licencia: {m.licencia} · {modo} · {m.tamano_mb} MB")
        if m.nota:
            lineas.append(f"    {m.nota}")
        lineas.append("")
    return "\n".join(lineas)
