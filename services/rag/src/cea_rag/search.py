"""Búsqueda híbrida sobre la base de conocimiento.

Léxica y densa a la vez, fusionadas con RRF. Ninguna de las dos basta sola:

- La densa entiende que "¿cuánto cobran al año?" pregunta por la membresía,
  pero se pierde con un identificador literal —un código de comisión, el nombre
  exacto de un producto— porque no lo ha visto en el entrenamiento.
- La léxica encuentra el literal exacto y no entiende la paráfrasis.

En una base bancaria las dos situaciones son diarias, así que se ejecutan las
dos y se fusionan.
"""

from __future__ import annotations

from dataclasses import dataclass

# Constante de la fusión recíproca de rangos.
#
# El 60 es el valor del artículo original y funciona como amortiguador: evita
# que el primer puesto de una lista aplaste al resto. Bajarlo hace la fusión
# más agresiva con los primeros resultados; subirlo la aplana.
K_RRF = 60


@dataclass(slots=True, frozen=True)
class Pasaje:
    """Un trozo recuperado, con su procedencia para poder citarlo."""

    chunk_id: str
    document_id: str
    documento: str
    section: str
    contenido: str
    puntuacion: float
    origen: str
    """De qué búsqueda vino: lexica, densa o ambas. Sirve para depurar por qué
    apareció algo y para medir cuánto aporta cada lado."""


def fusionar_rrf(
    lexica: list[str], densa: list[str], *, k: int = K_RRF
) -> dict[str, tuple[float, str]]:
    """Fusiona dos rankings por RRF.

    Se fusionan POSICIONES y no puntuaciones a propósito: la similitud coseno y
    el `ts_rank` de Postgres viven en escalas distintas y sin relación, así que
    sumarlas o normalizarlas exigiría calibrar dos distribuciones que además
    cambian con el corpus. La posición es comparable sin calibrar nada.
    """
    puntos: dict[str, float] = {}
    origenes: dict[str, set[str]] = {}

    for nombre, ranking in (("lexica", lexica), ("densa", densa)):
        for posicion, chunk_id in enumerate(ranking, start=1):
            puntos[chunk_id] = puntos.get(chunk_id, 0.0) + 1.0 / (k + posicion)
            origenes.setdefault(chunk_id, set()).add(nombre)

    return {
        cid: (valor, "ambas" if len(origenes[cid]) > 1 else next(iter(origenes[cid])))
        for cid, valor in puntos.items()
    }


# La consulta léxica usa OR sobre los lexemas, no AND.
#
# `websearch_to_tsquery` y `plainto_tsquery` unen los términos con AND, y una
# pregunta conversacional exige entonces que TODAS sus palabras aparezcan en el
# mismo trozo. Medido sobre esta base: "¿Cuánto cobran al año por la tarjeta
# Oro?" devolvía CERO resultados, porque ningún trozo contiene a la vez
# "cuanto", "cobran", "año", "por" y "tarjeta". El lado léxico quedaba muerto
# para todas las preguntas reales y la búsqueda dejaba de ser híbrida sin que
# nada fallara.
#
# Con OR, `ts_rank_cd` hace el trabajo: puntúa más alto a los trozos que cubren
# más términos y los tienen más cerca entre sí. `to_tsvector` se encarga de
# quitar vacías y de lematizar antes de armar la consulta.
SQL_LEXICA = """
    WITH consulta AS (
        SELECT array_to_string(
                   ARRAY(SELECT lexeme FROM unnest(to_tsvector('es_unaccent', %(consulta)s))),
                   ' | '
               ) AS expr
    )
    SELECT c.chunk_id
    FROM kb_chunks c, consulta q
    WHERE q.expr <> '' AND c.tsv @@ q.expr::tsquery
    ORDER BY ts_rank_cd(c.tsv, q.expr::tsquery) DESC
    LIMIT %(limite)s
"""

SQL_DENSA = """
    SELECT c.chunk_id
    FROM kb_chunks c
    WHERE c.embedding IS NOT NULL
    ORDER BY c.embedding <=> %(vector)s::vector
    LIMIT %(limite)s
"""

SQL_DETALLE = """
    SELECT c.chunk_id, c.document_id, d.title AS documento, c.section, c.content
    FROM kb_chunks c
    JOIN kb_documents d USING (document_id)
    WHERE c.chunk_id = ANY(%(ids)s)
"""


async def buscar(
    cur,
    consulta: str,
    vector: list[float] | None,
    *,
    candidatos: int = 30,
    devolver: int = 5,
) -> list[Pasaje]:
    """Recupera los pasajes más relevantes.

    Se piden `candidatos` por cada lado y se devuelven `devolver` tras fusionar.
    Recuperar ancho y recortar después es lo que permite que un documento que
    una de las dos búsquedas puso en el puesto veinte suba si la otra lo puso
    arriba.
    """
    await cur.execute(SQL_LEXICA, {"consulta": consulta, "limite": candidatos})
    lexica = [f["chunk_id"] for f in await cur.fetchall()]

    densa: list[str] = []
    if vector is not None:
        await cur.execute(SQL_DENSA, {"vector": str(vector), "limite": candidatos})
        densa = [f["chunk_id"] for f in await cur.fetchall()]

    fusionado = fusionar_rrf(lexica, densa)
    if not fusionado:
        return []

    mejores = sorted(fusionado.items(), key=lambda kv: kv[1][0], reverse=True)[:devolver]
    ids = [cid for cid, _ in mejores]

    await cur.execute(SQL_DETALLE, {"ids": ids})
    detalle = {f["chunk_id"]: f for f in await cur.fetchall()}

    return [
        Pasaje(
            chunk_id=cid,
            document_id=detalle[cid]["document_id"],
            documento=detalle[cid]["documento"],
            section=detalle[cid]["section"] or "",
            contenido=detalle[cid]["content"],
            puntuacion=round(puntos, 5),
            origen=origen,
        )
        for cid, (puntos, origen) in mejores
        if cid in detalle
    ]
