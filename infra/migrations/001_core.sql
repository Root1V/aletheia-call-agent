-- Esquema base del copiloto.
--
-- Migraciones en SQL plano y numerado, no en un ORM: en un banco el área de
-- seguridad y la de datos revisan el DDL, y deben poder leerlo sin ejecutar
-- Python.

BEGIN;

-- ──────────────────────────────────────────────────────────────────────────
-- Clientes y productos (Zona 6 del workspace: 360 bajo demanda)
-- ──────────────────────────────────────────────────────────────────────────

CREATE TABLE customers (
    customer_id       TEXT PRIMARY KEY,
    full_name         TEXT        NOT NULL,
    document_type     TEXT        NOT NULL DEFAULT 'DNI',
    -- Sólo enmascarado. El número completo no entra a este sistema: si no está,
    -- no se puede filtrar.
    document_masked   TEXT        NOT NULL,
    segment           TEXT        NOT NULL,
    customer_since    DATE        NOT NULL,
    birth_date        DATE,
    city              TEXT,
    district          TEXT,
    phone_masked      TEXT,
    email_masked      TEXT,
    nps               SMALLINT    CHECK (nps BETWEEN 0 AND 10),
    preferred_language TEXT       NOT NULL DEFAULT 'es-PE',
    -- Vulnerabilidad DECLARADA por el cliente. Inferirla queda en el backlog y
    -- exigiría consentimiento; en ningún caso puede usarse para precios u
    -- ofertas, sólo para adaptar el trato.
    vulnerabilities   TEXT[]      NOT NULL DEFAULT '{}',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE product_holdings (
    holding_id     TEXT PRIMARY KEY,
    customer_id    TEXT        NOT NULL REFERENCES customers ON DELETE CASCADE,
    product_code   TEXT        NOT NULL,
    product_name   TEXT        NOT NULL,
    opened_at      DATE        NOT NULL,
    balance        NUMERIC(14,2),
    credit_limit   NUMERIC(14,2),
    currency       TEXT        NOT NULL DEFAULT 'PEN',
    status         TEXT        NOT NULL DEFAULT 'activo',
    masked_number  TEXT
);
CREATE INDEX ON product_holdings (customer_id);

-- ──────────────────────────────────────────────────────────────────────────
-- Comercios y transacciones (Zona 2: la evidencia que resuelve la disputa)
-- ──────────────────────────────────────────────────────────────────────────

CREATE TABLE merchants (
    merchant_id         TEXT PRIMARY KEY,
    display_name        TEXT NOT NULL,
    legal_name          TEXT,
    category            TEXT NOT NULL,
    logo_url            TEXT,
    district            TEXT,
    city                TEXT,
    country             TEXT NOT NULL DEFAULT 'PE'
);

CREATE INDEX merchants_name_trgm
    ON merchants USING gin (display_name gin_trgm_ops);

-- Los patrones de descriptor viven en su propia tabla, una fila por patrón.
--
-- Resolver un descriptor crudo contra el catálogo es matching DIFUSO, no
-- igualdad: "DLO*RAPPI PE 5511234567" debe caer en Rappi aunque el sufijo
-- numérico cambie en cada compra. Con una fila por patrón el índice trigram es
-- directo y la similitud se calcula contra el patrón individual, que es lo que
-- se quiere puntuar; concatenar todos los patrones de un comercio en un solo
-- texto diluye la señal y además no es indexable (array_to_string no es
-- IMMUTABLE).
CREATE TABLE merchant_descriptors (
    descriptor_id BIGSERIAL PRIMARY KEY,
    merchant_id   TEXT NOT NULL REFERENCES merchants ON DELETE CASCADE,
    pattern       TEXT NOT NULL,
    UNIQUE (merchant_id, pattern)
);
CREATE INDEX merchant_descriptors_trgm
    ON merchant_descriptors USING gin (pattern gin_trgm_ops);

CREATE TABLE transactions (
    transaction_id      TEXT PRIMARY KEY,
    account_id          TEXT        NOT NULL,
    customer_id         TEXT        NOT NULL REFERENCES customers ON DELETE CASCADE,
    occurred_at         TIMESTAMPTZ NOT NULL,
    amount              NUMERIC(14,2) NOT NULL,
    currency            TEXT        NOT NULL DEFAULT 'PEN',
    status              TEXT        NOT NULL,
    channel             TEXT        NOT NULL,
    -- Lo que el cliente ve en su estado de cuenta. Se conserva a propósito: el
    -- ejecutivo necesita tender el puente entre ese texto ilegible y el
    -- comercio real.
    raw_descriptor      TEXT        NOT NULL,
    merchant_id         TEXT        REFERENCES merchants,
    device_label        TEXT,
    decline_reason      TEXT,
    prior_purchases_90d INTEGER     NOT NULL DEFAULT 0,
    is_recurring        BOOLEAN     NOT NULL DEFAULT false
);
CREATE INDEX ON transactions (customer_id, occurred_at DESC);
CREATE INDEX ON transactions (merchant_id);

-- ──────────────────────────────────────────────────────────────────────────
-- Zona 1: por qué llama
-- ──────────────────────────────────────────────────────────────────────────

CREATE TABLE account_events (
    event_id              BIGSERIAL PRIMARY KEY,
    customer_id           TEXT        NOT NULL REFERENCES customers ON DELETE CASCADE,
    occurred_at           TIMESTAMPTZ NOT NULL,
    kind                  TEXT        NOT NULL,
    summary               TEXT        NOT NULL,
    related_transaction_id TEXT       REFERENCES transactions,
    severity              TEXT        NOT NULL DEFAULT 'info'
);
CREATE INDEX ON account_events (customer_id, occurred_at DESC);

CREATE TABLE digital_journey_events (
    event_id    BIGSERIAL PRIMARY KEY,
    customer_id TEXT        NOT NULL REFERENCES customers ON DELETE CASCADE,
    occurred_at TIMESTAMPTZ NOT NULL,
    channel     TEXT        NOT NULL,
    screen      TEXT        NOT NULL,
    action      TEXT        NOT NULL,
    succeeded   BOOLEAN     NOT NULL,
    detail      TEXT
);
CREATE INDEX ON digital_journey_events (customer_id, occurred_at DESC);

-- ──────────────────────────────────────────────────────────────────────────
-- Reclamos (Ley 31763)
-- ──────────────────────────────────────────────────────────────────────────

CREATE TABLE cases (
    case_id                TEXT PRIMARY KEY,
    folio                  TEXT        NOT NULL UNIQUE,
    customer_id            TEXT        NOT NULL REFERENCES customers ON DELETE CASCADE,
    -- RECLAMO: presunta afectación de un interés legítimo.
    -- REQUERIMIENTO: solicitud de una acción de la empresa.
    -- Clasificar mal un reclamo como requerimiento es un incumplimiento frente
    -- a la SBS, por eso el tipo está restringido en la propia base.
    case_type              TEXT        NOT NULL CHECK (case_type IN ('reclamo','requerimiento')),
    status                 TEXT        NOT NULL,
    opened_at              TIMESTAMPTZ NOT NULL,
    -- 15 días hábiles desde la apertura, en calendario de Lima.
    due_at                 TIMESTAMPTZ NOT NULL,
    subject                TEXT        NOT NULL,
    summary                TEXT,
    related_transaction_id TEXT        REFERENCES transactions,
    CONSTRAINT plazo_posterior_a_apertura CHECK (due_at > opened_at)
);
CREATE INDEX ON cases (customer_id, status);
CREATE INDEX ON cases (due_at) WHERE status NOT IN ('resuelto','cerrado');

COMMIT;
