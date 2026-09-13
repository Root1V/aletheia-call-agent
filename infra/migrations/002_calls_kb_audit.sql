-- Llamadas, base de conocimiento y auditoría.

BEGIN;

-- ──────────────────────────────────────────────────────────────────────────
-- Llamadas y event sourcing
-- ──────────────────────────────────────────────────────────────────────────

CREATE TABLE calls (
    call_id      TEXT PRIMARY KEY,
    customer_id  TEXT        NOT NULL REFERENCES customers,
    agent_id     TEXT        NOT NULL,
    room         TEXT        NOT NULL,
    ingress      TEXT        NOT NULL,
    started_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at     TIMESTAMPTZ,
    scenario_id  TEXT,
    disposition  TEXT,
    summary      TEXT
);
CREATE INDEX ON calls (customer_id, started_at DESC);

-- El log de eventos ES la llamada.
--
-- Guardar el flujo completo en vez de sólo el resultado da tres cosas que
-- valen más que cualquier modelo: reproducir una llamada para depurarla,
-- correr evaluaciones deterministas sobre tráfico real, y auditar qué vio el
-- ejecutivo en cada instante. Reconstruir eso después, a partir de tablas
-- normalizadas por tipo de evento, no se puede.
CREATE TABLE call_events (
    call_id  TEXT        NOT NULL REFERENCES calls ON DELETE CASCADE,
    seq      INTEGER     NOT NULL,
    ts_ms    BIGINT      NOT NULL,
    type     TEXT        NOT NULL,
    event_id TEXT        NOT NULL,
    -- El evento completo tal como viajó por el bus, validado contra
    -- cea_contracts. Si el esquema evoluciona, el replay de llamadas viejas
    -- sigue funcionando porque el payload conserva su forma original.
    payload  JSONB       NOT NULL,
    PRIMARY KEY (call_id, seq)
);
CREATE INDEX ON call_events (call_id, type);
CREATE INDEX ON call_events (type, ts_ms DESC);

-- Serie de emoción aparte del log.
--
-- Llega a 2 Hz y se consulta por rango de tiempo para pintar las barras;
-- filtrarla desde el JSONB del log en cada consulta sería trabajo repetido.
-- Sólo del CLIENTE: no existe columna de hablante porque no hay otro caso.
CREATE TABLE emotion_timeline (
    call_id     TEXT        NOT NULL REFERENCES calls ON DELETE CASCADE,
    ts_ms       BIGINT      NOT NULL,
    valence     REAL        NOT NULL CHECK (valence BETWEEN -1 AND 1),
    arousal     REAL        NOT NULL CHECK (arousal BETWEEN -1 AND 1),
    dominance   REAL        CHECK (dominance BETWEEN -1 AND 1),
    scores      JSONB       NOT NULL,
    confidence  REAL        NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    PRIMARY KEY (call_id, ts_ms)
);

-- ──────────────────────────────────────────────────────────────────────────
-- Base de conocimiento (RAG híbrido)
-- ──────────────────────────────────────────────────────────────────────────

CREATE TABLE kb_documents (
    document_id TEXT PRIMARY KEY,
    title       TEXT        NOT NULL,
    kind        TEXT        NOT NULL,   -- tarifario | procedimiento | politica | contrato
    version     TEXT        NOT NULL,
    effective_from DATE     NOT NULL,
    source_url  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE kb_chunks (
    chunk_id    TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES kb_documents ON DELETE CASCADE,
    section     TEXT,
    ordinal     INTEGER NOT NULL,
    content     TEXT    NOT NULL,
    -- 1024 dimensiones: es lo que producen los modelos multilingües abiertos
    -- de referencia (bge-m3). Cambiar de modelo obliga a reindexar, así que la
    -- dimensión se fija aquí de forma deliberada y no por conveniencia.
    embedding   vector(1024),
    -- Lado léxico de la búsqueda híbrida. Se materializa como columna generada
    -- para que el índice GIN no se recalcule en cada consulta.
    tsv         tsvector GENERATED ALWAYS AS (to_tsvector('es_unaccent', content)) STORED
);
CREATE INDEX kb_chunks_tsv ON kb_chunks USING gin (tsv);
CREATE INDEX kb_chunks_embedding ON kb_chunks
    USING hnsw (embedding vector_cosine_ops);

-- Las cifras citables viven aparte del texto, en forma estructurada.
--
-- Es el control que evita el incidente regulatorio: cuando el LLM emite una
-- tasa, una comisión o un plazo, se contrasta contra ESTA tabla. Si no
-- coincide, la tarjeta se bloquea. No es el prompt lo que impide inventar una
-- tarifa: es esta verificación.
CREATE TABLE kb_facts (
    fact_id     TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES kb_documents ON DELETE CASCADE,
    product_code TEXT,
    key         TEXT    NOT NULL,       -- tea | tcea | comision_mantenimiento | plazo_reclamo
    value       NUMERIC NOT NULL,
    unit        TEXT    NOT NULL,       -- porcentaje | pen | usd | dias_habiles
    notes       TEXT,
    UNIQUE (document_id, product_code, key)
);

-- ──────────────────────────────────────────────────────────────────────────
-- Auditoría
-- ──────────────────────────────────────────────────────────────────────────

-- Qué sugirió la IA y qué hizo el ejecutivo con ello.
--
-- En un banco, "la IA lo recomendó" no exime de nada: tiene que poder
-- reconstruirse quién decidió qué, con qué respaldo y en qué momento.
CREATE TABLE audit_log (
    audit_id    BIGSERIAL PRIMARY KEY,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    call_id     TEXT        REFERENCES calls ON DELETE SET NULL,
    agent_id    TEXT        NOT NULL,
    action      TEXT        NOT NULL,   -- suggestion_shown | suggestion_used | case_classified ...
    subject     TEXT,
    ai_proposed JSONB,
    human_final JSONB,
    citations   JSONB
);
CREATE INDEX ON audit_log (call_id, occurred_at);
CREATE INDEX ON audit_log (agent_id, occurred_at DESC);

COMMIT;
