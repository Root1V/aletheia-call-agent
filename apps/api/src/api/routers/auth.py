"""Inicio de sesión y sesión vigente."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..auth import CurrentAgent, get_auth_provider

router = APIRouter(prefix="/api/auth", tags=["autenticación"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=256)


class AgentOut(BaseModel):
    agent_id: str
    username: str
    name: str
    roles: list[str]


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    agent: AgentOut


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest) -> LoginResponse:
    """Emite un token a partir de usuario y contraseña.

    No existe un endpoint de registro: las altas son una acción administrativa
    y el primer usuario se crea con `scripts/create_admin.py`. En una
    herramienta interna no hay caso de uso para el auto-registro, y quitarlo
    elimina la enumeración de cuentas, la confirmación por correo y la
    recuperación abierta como superficies de ataque.
    """
    emitido = await get_auth_provider().password_login(body.username, body.password)
    return LoginResponse(
        access_token=emitido.token,
        expires_in=emitido.expires_in,
        agent=AgentOut(
            agent_id=emitido.identity.agent_id,
            username=emitido.identity.username,
            name=emitido.identity.name,
            roles=sorted(emitido.identity.roles),
        ),
    )


@router.get("/me", response_model=AgentOut)
async def me(agent: CurrentAgent) -> AgentOut:
    """Sesión vigente. El portal la consulta al arrancar para saber si el token sirve."""
    return AgentOut(
        agent_id=agent.agent_id,
        username=agent.username,
        name=agent.name,
        roles=sorted(agent.roles),
    )
