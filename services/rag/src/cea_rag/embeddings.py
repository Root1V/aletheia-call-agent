"""Embeddings de consulta y de documento.

Viven aparte de la indexación porque la búsqueda en vivo los necesita en el
camino crítico de la sugerencia: un módulo que arrastre el lector de ficheros y
el troceado sólo para vectorizar una frase obliga al orquestador a importar
todo eso para nada.
"""

from __future__ import annotations

from cea_llm import AxoniumProvider

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
    """Vector de una consulta, o None si la plataforma no responde.

    Devolver None en lugar de propagar es deliberado: la búsqueda es híbrida y
    la mitad léxica sigue funcionando sin vector. Que el copiloto conteste algo
    peor es mejor que no conteste, y el fallo queda en el log.
    """
    vectores = await embeber(proveedor, [texto], modelo)
    return vectores[0] if vectores else None
