"""Indexación de la base de conocimiento."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import psycopg
from cea_llm import AxoniumProvider

from .chunking import Trozo, leer_documento, trocear
from .embeddings import MODELO_POR_DEFECTO, embeber
from .hechos import extraer

log = logging.getLogger("cea.rag")


@dataclass(slots=True)
class Informe:
    documentos: int = 0
    trozos: int = 0
    hechos: int = 0

    def __str__(self) -> str:
        return f"documentos={self.documentos} trozos={self.trozos} hechos={self.hechos}"


async def indexar(
    directorio: Path,
    dsn: str,
    *,
    modelo_embedding: str = MODELO_POR_DEFECTO,
    proveedor: AxoniumProvider | None = None,
) -> Informe:
    """Lee, trocea, embebe e inserta la base de conocimiento.

    Vacía y recarga. Una base de conocimiento de un banco cambia por versiones
    completas del tarifario o del procedimiento, no por parches sueltos, y
    reindexar entera evita quedarse con trozos huérfanos de una versión
    anterior citables como si estuvieran vigentes.
    """
    informe = Informe()
    propio = proveedor is None
    proveedor = proveedor or AxoniumProvider()

    archivos = sorted(directorio.glob("*.md"))
    if not archivos:
        raise FileNotFoundError(f"No hay documentos .md en {directorio}")

    try:
        documentos = []
        todos_trozos: list[Trozo] = []
        todos_hechos = []

        for ruta in archivos:
            doc = leer_documento(ruta.read_text())
            documentos.append(doc)
            todos_trozos.extend(trocear(doc))
            todos_hechos.extend(extraer(doc.document_id, doc.cuerpo))

        vectores = await embeber(proveedor, [t.contenido for t in todos_trozos], modelo_embedding)

        with psycopg.connect(dsn) as conn, conn.cursor() as cur:
            cur.execute("TRUNCATE kb_facts, kb_chunks, kb_documents CASCADE")

            cur.executemany(
                """
                INSERT INTO kb_documents (document_id, title, kind, version, effective_from)
                VALUES (%s, %s, %s, %s, %s)
                """,
                [(d.document_id, d.title, d.kind, d.version, d.effective_from) for d in documentos],
            )
            informe.documentos = len(documentos)

            cur.executemany(
                """
                INSERT INTO kb_chunks (chunk_id, document_id, section, ordinal, content, embedding)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                [
                    (t.chunk_id, t.document_id, t.section, t.ordinal, t.contenido, str(v))
                    for t, v in zip(todos_trozos, vectores, strict=True)
                ],
            )
            informe.trozos = len(todos_trozos)

            cur.executemany(
                """
                INSERT INTO kb_facts (fact_id, document_id, product_code, key, value, unit, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (fact_id) DO NOTHING
                """,
                [
                    (h.fact_id, h.document_id, h.product_code, h.clave, h.valor, h.unidad, h.nota)
                    for h in todos_hechos
                ],
            )
            informe.hechos = len(todos_hechos)
            conn.commit()
    finally:
        if propio:
            await proveedor.aclose()

    return informe
