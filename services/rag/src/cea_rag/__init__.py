"""Búsqueda híbrida sobre la base de conocimiento del banco."""

from .chunking import Documento, Trozo, leer_documento, trocear
from .embeddings import MODELO_POR_DEFECTO, embeber, embeber_consulta
from .hechos import Hecho, extraer
from .ingest import Informe, indexar
from .search import K_RRF, Pasaje, buscar, fusionar_rrf

__all__ = [
    "K_RRF",
    "MODELO_POR_DEFECTO",
    "Documento",
    "Hecho",
    "Informe",
    "Pasaje",
    "Trozo",
    "buscar",
    "embeber",
    "embeber_consulta",
    "extraer",
    "fusionar_rrf",
    "indexar",
    "leer_documento",
    "trocear",
]
