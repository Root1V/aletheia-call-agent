"""Aplicación FastAPI del workspace del ejecutivo."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import close_pool, open_pool
from .routers import calls, health

log = logging.getLogger("cea.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    if settings.auth_mode == "dev":
        # Avisar fuerte y en cada arranque. El modo dev es cómodo, y por eso es
        # exactamente el que se hereda por descuido a un entorno compartido.
        log.warning(
            "AUTENTICACIÓN EN MODO DEV: las peticiones no se verifican. "
            "No usar fuera de la máquina del desarrollador (CEA_AUTH_MODE=oidc)."
        )

    await open_pool(settings.database_url)
    try:
        yield
    finally:
        await close_pool()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Copiloto de Atención al Cliente",
        description=(
            "API del workspace del ejecutivo. Perímetro: banca peruana "
            "(SBS / Indecopi). Todo el stack es open source y auto-hospedable."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(calls.router)
    return app


app = create_app()
