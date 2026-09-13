-- Escenarios de demostración y evaluación.
--
-- Mapea cada guion reproducible al cliente sintético que le corresponde. Es lo
-- que permite que la bandeja de llamadas entrantes del portal sea determinista
-- y que el golden set y la demo usen exactamente los mismos datos.

BEGIN;

CREATE TABLE demo_scenarios (
    scenario_id          TEXT PRIMARY KEY,
    customer_id          TEXT NOT NULL REFERENCES customers ON DELETE CASCADE,
    expected_intent      TEXT NOT NULL,
    focus_transaction_id TEXT REFERENCES transactions,
    -- Qué está pasando, en una línea. Se muestra en la bandeja de demo y se
    -- usa como descripción del caso en los informes de evaluación.
    narrative            TEXT NOT NULL,
    -- Clasificación correcta bajo la Ley 31763 cuando el escenario deriva en
    -- caso. NULL cuando no corresponde abrir ninguno: ese "ninguno" es
    -- justamente el resultado esperado del cargo mal entendido, y el evaluador
    -- tiene que poder distinguirlo de "no se sabe".
    expected_case_type   TEXT CHECK (expected_case_type IN ('reclamo','requerimiento')),
    expects_case         BOOLEAN NOT NULL DEFAULT true,
    ordinal              SMALLINT NOT NULL
);

COMMIT;
