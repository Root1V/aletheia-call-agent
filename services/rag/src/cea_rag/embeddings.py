"""Embeddings de consulta y de documento.

Viven aparte de la indexación porque la búsqueda en vivo los necesita en el
camino crítico de la sugerencia: un módulo que arrastre el lector de ficheros y
el troceado sólo para vectorizar una frase obliga al orquestador a importar
todo eso para nada.
"""

from __future__ import annotations

import logging

from axonium import AxoniumError
from cea_llm import AxoniumProvider

log = logging.getLogger("cea.rag")

# Modelo de embeddings por defecto.
#
# Tiene que ser EL MISMO con el que se indexó: dos modelos distintos producen
# espacios distintos, y la búsqueda densa devuelve resultados plausibles pero
# incorrectos sin fallar en ningún sitio. Por eso es una constante compartida
# entre indexación y consulta, no un valor por defecto repetido en cada firma.
MODELO_POR_DEFECTO = "qwen3-embedding"

# Tamaño de lote. Medido contra la plataforma: una petición suelta cuesta unos
# 480 ms por el arranque en frío, y en lote baja a 7 ms por texto.
LOTE = 32


async def embeber(
    proveedor: AxoniumProvider,
    textos: list[str],
    modelo: str = MODELO_POR_DEFECTO,
) -> list[list[float]]:
    cliente = proveedor._construir()  # noqa: SLF001 - el SDK expone embeddings aparte
    vectores: list[list[float]] = []
    for i in range(0, len(textos), LOTE):
        r = await cliente.embeddings.create(model=modelo, input=textos[i : i + LOTE])
        vectores.extend(d.embedding for d in r.data)
    return vectores


async def embeber_consulta(
    proveedor: AxoniumProvider,
    texto: str,
    modelo: str = MODELO_POR_DEFECTO,
) -> list[float] | None:
    """Vector de una consulta, o None si la plataforma no lo puede dar.

    Devolver None en lugar de propagar es deliberado: la búsqueda es híbrida y
    la mitad léxica sigue funcionando sin vector. Que el copiloto conteste algo
    peor es mejor que no conteste, y el fallo queda en el log.

    Importa sobre todo cuando se agota el cupo: `embeddings` y `rerank`
    comparten presupuesto de peticiones y `chat` tiene el suyo, así que quedarse
    sin vector NO significa quedarse sin sugerencia. Significa una sugerencia
    con los pasajes peor ordenados, que es una degradación y no una caída.

    Sólo se traga el fallo DE LA PLATAFORMA. Un error de programación aquí
    —un modelo mal escrito, un tipo equivocado— tiene que llegar arriba y
    romper, no convertirse en una búsqueda silenciosamente peor.
    """
    try:
        vectores = await embeber(proveedor, [texto], modelo)
    except AxoniumError:
        log.warning("Sin embedding de consulta; se busca sólo por léxico", exc_info=True)
        return None
    return vectores[0] if vectores else None
