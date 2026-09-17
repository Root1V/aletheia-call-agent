"""Reordenamiento con un cross-encoder.

La fusión RRF ordena por POSICIÓN en dos listas, que es lo correcto cuando no se
pueden comparar las puntuaciones, pero nunca mira la consulta y el pasaje
juntos. Un cross-encoder sí: los codifica en la misma pasada y devuelve cuánto
responde ese pasaje a esa pregunta.

Por qué importa aquí y no en cualquier buscador: el cliente no habla como está
escrito el documento. Dice "¿cuánto me cobran por sacar plata del cajero?" y el
tarifario dice "comisión por disposición de efectivo". La búsqueda densa cubre
parte de esa distancia; el reordenador cubre la que queda, y además empuja
abajo lo que entró por una coincidencia léxica casual.

El coste es una llamada más en el camino crítico de la sugerencia, así que el
reordenador es OPCIONAL: sin él la búsqueda sigue funcionando y devuelve el
orden de RRF.
"""

from __future__ import annotations

import logging

from cea_llm import AxoniumProvider

from .search import Pasaje

log = logging.getLogger("cea.rag")

MODELO_POR_DEFECTO = "qwen3-reranker"

# Cuántos candidatos de RRF se reordenan.
#
# El coste es lineal y medido: ~26 ms por trozo de ~200 tokens, de forma muy
# estable entre 3 y 39 documentos. Reordenar 30 candidatos son ~780 ms, que se
# come medio presupuesto de la sugerencia.
#
# Sobre la base actual —trece trozos— reordenar los tres primeros da ya el
# resultado completo: acierto@1 pasa de 54% a 85% y no mejora más con
# profundidades mayores. **Ese número no se puede llevar a producción tal
# cual**: con trece trozos RRF casi siempre mete el correcto entre los tres
# primeros, y en una base bancaria de miles el pasaje correcto aparece con
# frecuencia en el puesto diez o quince. Diez es el compromiso: cubre ese caso
# por ~260 ms en lugar de ~780, y habrá que volver a medirlo con la base real
# del banco antes de fijarlo.
PROFUNDIDAD = 10

# Cuánto del pasaje se le entrega al reordenador.
#
# Los trozos rondan los 400 caracteres, así que en la práctica no recorta nada.
# El tope existe para que un documento mal troceado —una tabla larga que no se
# pudo partir— no haga crecer la petición sin control: el reordenador cobra por
# tokens de entrada y todo el conjunto viaja en una sola petición.
MAXIMO_CARACTERES = 1200


async def reordenar(
    proveedor: AxoniumProvider,
    consulta: str,
    pasajes: list[Pasaje],
    *,
    devolver: int = 5,
    profundidad: int = PROFUNDIDAD,
    modelo: str = MODELO_POR_DEFECTO,
) -> list[Pasaje]:
    """Reordena los pasajes por relevancia real a la consulta.

    Si la plataforma falla se devuelve el orden de RRF recortado. Es una
    degradación, no un fallo: una sugerencia con los pasajes peor ordenados
    sigue siendo mejor que ninguna sugerencia, y el aviso queda en el log.
    """
    if len(pasajes) <= 1:
        return pasajes[:devolver]

    # Lo que queda fuera de la profundidad NO se descarta: se deja detrás de lo
    # reordenado. Si el reordenador tuviera un mal día, el resultado sigue
    # siendo el de RRF y no una lista truncada.
    cabeza, cola = pasajes[:profundidad], pasajes[profundidad:]
    pasajes = cabeza

    cliente = proveedor._construir()  # noqa: SLF001 - el SDK expone rerank aparte
    try:
        respuesta = await cliente.rerank.create(
            model=modelo,
            query=consulta,
            documents=[p.contenido[:MAXIMO_CARACTERES] for p in pasajes],
            top_n=devolver,
        )
    except Exception:  # noqa: BLE001
        log.warning("El reordenador no respondió; se mantiene el orden de RRF", exc_info=True)
        return (pasajes + cola)[:devolver]

    # La puntuación del cross-encoder SUSTITUYE a la de RRF, no se combina con
    # ella. Son escalas sin relación —una es una suma de inversos de posición,
    # la otra una probabilidad— y mezclarlas exigiría calibrar dos
    # distribuciones que cambian con el corpus.
    reordenados = [
        Pasaje(
            chunk_id=p.chunk_id,
            document_id=p.document_id,
            documento=p.documento,
            section=p.section,
            contenido=p.contenido,
            puntuacion=round(float(r.relevance_score), 5),
            origen=f"{p.origen}+rerank",
        )
        for r in respuesta.results
        if r.index is not None and (p := pasajes[r.index])
    ]
    return (reordenados + cola)[:devolver]
