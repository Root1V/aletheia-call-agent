"""Tests de autenticación.

Cubren sobre todo las propiedades de seguridad, que son las que se rompen sin
hacer ruido: un cambio inocente en el manejo de errores puede convertir el
login en un oráculo para enumerar cuentas sin que nada falle visiblemente.
"""

from __future__ import annotations

import time

import pytest
from api.auth.base import AgentIdentity
from api.auth.local import LocalAuthProvider, hash_password
from api.config import SECRETO_DE_DESARROLLO, Settings
from api.db import cursor
from fastapi import HTTPException

from .conftest import requiere_datos

pytestmark = requiere_datos

SECRETO = "secreto-de-pruebas-suficientemente-largo-para-hs256"


@pytest.fixture
async def usuario(db):
    """Un usuario desechable, borrado al terminar."""
    async with cursor() as cur:
        await cur.execute(
            """
            INSERT INTO users (user_id, username, full_name, password_hash, roles)
            VALUES ('usr_test', 'test_user', 'Usuario de Prueba', %s, ARRAY['ejecutivo'])
            ON CONFLICT (username) DO UPDATE SET password_hash = EXCLUDED.password_hash,
                                                 is_active = true
            """,
            (hash_password("contraseña-de-prueba-larga"),),
        )
    yield "test_user"
    async with cursor() as cur:
        await cur.execute("DELETE FROM users WHERE user_id = 'usr_test'")


async def test_login_correcto_emite_token_utilizable(usuario) -> None:
    provider = LocalAuthProvider(SECRETO)

    emitido = await provider.password_login(usuario, "contraseña-de-prueba-larga")
    recuperada = await provider.verify_token(emitido.token)

    assert recuperada.username == "test_user"
    assert "ejecutivo" in recuperada.roles
    assert emitido.expires_in > 0


async def test_contrasena_incorrecta_y_usuario_inexistente_dan_el_mismo_error(usuario) -> None:
    """Mensajes distintos convierten el login en un directorio de cuentas válidas."""
    provider = LocalAuthProvider(SECRETO)

    with pytest.raises(HTTPException) as mala_clave:
        await provider.password_login(usuario, "clave-equivocada")
    with pytest.raises(HTTPException) as sin_usuario:
        await provider.password_login("no_existe_este_usuario", "clave-equivocada")

    assert mala_clave.value.status_code == sin_usuario.value.status_code == 401
    assert mala_clave.value.detail == sin_usuario.value.detail


async def test_el_tiempo_de_respuesta_no_delata_que_usuarios_existen(usuario) -> None:
    """Sin el hash señuelo, el usuario inexistente responde en microsegundos.

    Esa diferencia frente a los ~200 ms que tarda bcrypt basta para enumerar
    cuentas válidas cronometrando las respuestas.
    """
    provider = LocalAuthProvider(SECRETO)

    async def medir(username: str) -> float:
        inicio = time.perf_counter()
        with pytest.raises(HTTPException):
            await provider.password_login(username, "clave-equivocada")
        return time.perf_counter() - inicio

    existente = min([await medir(usuario) for _ in range(3)])
    inexistente = min([await medir("no_existe_este_usuario") for _ in range(3)])

    proporcion = max(existente, inexistente) / min(existente, inexistente)
    assert proporcion < 2.0, f"el tiempo delata la existencia de la cuenta (x{proporcion:.1f})"


async def test_una_cuenta_desactivada_no_puede_entrar(usuario) -> None:
    provider = LocalAuthProvider(SECRETO)
    async with cursor() as cur:
        await cur.execute("UPDATE users SET is_active = false WHERE username = %s", (usuario,))

    with pytest.raises(HTTPException) as exc:
        await provider.password_login(usuario, "contraseña-de-prueba-larga")

    assert exc.value.status_code == 401


async def test_un_token_firmado_con_otro_secreto_se_rechaza(usuario) -> None:
    """Es la comprobación que hace que el secreto valga algo."""
    emisor = LocalAuthProvider("un-secreto-completamente-distinto-de-pruebas")
    verificador = LocalAuthProvider(SECRETO)
    emitido = await emisor.password_login(usuario, "contraseña-de-prueba-larga")

    with pytest.raises(HTTPException) as exc:
        await verificador.verify_token(emitido.token)

    assert exc.value.status_code == 401


async def test_un_token_expirado_se_rechaza(usuario) -> None:
    provider = LocalAuthProvider(SECRETO, ttl_hours=0)
    emitido = await provider.password_login(usuario, "contraseña-de-prueba-larga")

    time.sleep(1.1)
    with pytest.raises(HTTPException) as exc:
        await provider.verify_token(emitido.token)

    assert exc.value.status_code == 401


def test_la_api_no_arranca_en_produccion_con_el_secreto_de_desarrollo() -> None:
    """Un secreto de firma público permite emitir tokens de cualquier usuario.

    Se comprueba aquí y no sólo en el arranque porque es el tipo de salvaguarda
    que alguien desactiva "temporalmente" para desbloquear un despliegue.
    """
    assert (
        Settings(environment="dev", jwt_secret=SECRETO_DE_DESARROLLO).validar_para_arranque() == []
    )

    for entorno in ("staging", "prod"):
        problemas = Settings(
            environment=entorno, jwt_secret=SECRETO_DE_DESARROLLO
        ).validar_para_arranque()
        assert problemas, f"{entorno} aceptó el secreto de desarrollo"

    assert Settings(environment="prod", jwt_secret="x" * 64).validar_para_arranque() == []


def test_la_identidad_exige_el_rol_correcto() -> None:
    identidad = AgentIdentity(agent_id="u1", username="u", name="U", roles=frozenset({"ejecutivo"}))

    identidad.require("ejecutivo")
    with pytest.raises(HTTPException) as exc:
        identidad.require("supervisor")
    assert exc.value.status_code == 403
