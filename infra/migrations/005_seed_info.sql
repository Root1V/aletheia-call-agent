-- Cuándo se sembraron los datos de demostración.
--
-- Los escenarios colocan sus eventos en relación al momento de la siembra
-- ("el cargo fue hace veinte horas"), y el contexto de llamada sólo mira las
-- últimas 72 horas. Pasados unos días, esos eventos salen de la ventana y el
-- panel aparece VACÍO sin ningún error: parece que el producto no funciona
-- cuando lo único que pasa es que los datos caducaron.
--
-- Con esta marca, el portal puede avisar en lugar de degradarse en silencio.

BEGIN;

CREATE TABLE seed_info (
    -- Una sola fila. La restricción lo garantiza en vez de confiar en que
    -- nadie inserte otra.
    id         BOOLEAN PRIMARY KEY DEFAULT true CHECK (id),
    seeded_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    seed_value INTEGER     NOT NULL
);

COMMIT;
