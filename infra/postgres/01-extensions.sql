-- Extensiones necesarias antes de cualquier migración.
--
-- pgvector vive en el MISMO Postgres que los datos transaccionales a propósito:
-- para el volumen de una base de conocimiento bancaria (muy por debajo de 5-10M
-- vectores) una base vectorial aparte sólo añade operación. Qdrant entra si se
-- supera esa escala.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;      -- matching difuso de descriptores de comercio
CREATE EXTENSION IF NOT EXISTS unaccent;     -- búsqueda en español sin tildes

-- Configuración de búsqueda de texto en español, para el lado léxico (BM25)
-- de la búsqueda híbrida.
CREATE TEXT SEARCH CONFIGURATION es_unaccent (COPY = spanish);
ALTER TEXT SEARCH CONFIGURATION es_unaccent
    ALTER MAPPING FOR hword, hword_part, word
    WITH unaccent, spanish_stem;
