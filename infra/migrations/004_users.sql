-- Usuarios del portal.
--
-- No hay endpoint público de registro: el primer administrador se crea con
-- `scripts/create_admin.py` y a partir de ahí las altas son una acción
-- administrativa. En una herramienta interna de un banco no hay ningún caso de
-- uso para el auto-registro, y quitarlo elimina toda una superficie de ataque
-- (enumeración de cuentas, confirmaciones por correo, recuperación abierta).

BEGIN;

CREATE TABLE users (
    user_id       TEXT PRIMARY KEY,
    username      TEXT        NOT NULL UNIQUE,
    email         TEXT        UNIQUE,
    full_name     TEXT        NOT NULL,
    -- Hash bcrypt. La contraseña en claro no existe en ningún punto del
    -- sistema: llega en el cuerpo del login por TLS y se descarta tras
    -- verificar.
    password_hash TEXT        NOT NULL,
    roles         TEXT[]      NOT NULL DEFAULT '{ejecutivo}',
    is_active     BOOLEAN     NOT NULL DEFAULT true,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at TIMESTAMPTZ,
    CONSTRAINT roles_no_vacio CHECK (cardinality(roles) > 0)
);

-- Búsqueda por nombre de usuario sin distinguir mayúsculas: escribir "Carlos"
-- o "carlos" no puede ser la diferencia entre entrar y no entrar.
CREATE UNIQUE INDEX users_username_lower ON users (lower(username));

COMMIT;
