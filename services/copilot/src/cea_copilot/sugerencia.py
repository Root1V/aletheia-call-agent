"""Generación de la sugerencia, de extremo a extremo."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from cea_contracts import Citation
from cea_llm import ProveedorLLM
from cea_rag import Pasaje, buscar

from .guardarrailes import Resultado, evaluar
from .prompt import Contexto, construir

log = logging.getLogger("cea.copilot")

# Cuántos pasajes se le entregan al modelo.
#
# Cinco es el equilibrio: con menos se queda sin material para preguntas que
# cruzan dos documentos, y con más el modelo empieza a mezclar procedimientos
# distintos en la misma frase. Se recuperan treinta candidatos y se recortan
# tras fusionar.
PASAJES = 5
CANDIDATOS = 30

# Tope de la generación. Cuarenta palabras son unos 60 tokens en español; el
# margen deja sitio para que termine la frase en vez de cortarla.
MAX_TOKENS = 110


@dataclass(slots=True, frozen=True)
class Sugerencia:
    texto: str
    citas: tuple[Citation, ...]
    guardarrailes: Resultado
    latencia_ms: float
    ttft_ms: float
    modelo: str

    @property
    def mostrable(self) -> bool:
        return self.guardarrailes.aprobada


async def _cifras_citables(cur, ids_documentos: set[str]) -> list[tuple[float, str]]:
    """Cifras del tarifario de los documentos que se le pasaron al modelo.

    Sólo de esos: si una comisión no estaba entre el material entregado, el
    modelo no pudo leerla, y aceptarla porque existe en otro documento sería
    dar por buena una coincidencia.
    """
    if not ids_documentos:
        return []
    await cur.execute(
        "SELECT value, unit FROM kb_facts WHERE document_id = ANY(%s)",
        (list(ids_documentos),),
    )
    return [(float(f["value"]), f["unit"]) for f in await cur.fetchall()]


async def generar(
    cur,
    proveedor: ProveedorLLM,
    *,
    turno_del_cliente: str,
    datos_de_la_llamada: str,
    consulta_kb: str | None = None,
    vector: list[float] | None = None,
    tono: str | None = None,
) -> Sugerencia:
    """Recupera, genera y verifica.

    El orden importa: la verificación ocurre sobre el texto ya generado y
    ANTES de publicarlo. Una sugerencia bloqueada no llega al portal; llega el
    motivo, para que el ejecutivo sepa que el copiloto se calló a propósito y
    no que se quedó colgado.
    """
    inicio = time.perf_counter()

    consulta = consulta_kb or turno_del_cliente
    pasajes: tuple[Pasaje, ...] = tuple(
        await buscar(cur, consulta, vector, candidatos=CANDIDATOS, devolver=PASAJES)
    )

    ctx = Contexto(
        turno_del_cliente=turno_del_cliente,
        datos_de_la_llamada=datos_de_la_llamada,
        pasajes=pasajes,
        tono=tono,
    )

    ttft = 0.0
    trozos: list[str] = []
    t_gen = time.perf_counter()
    async for fragmento in proveedor.transmitir(
        construir(ctx), max_tokens=MAX_TOKENS, temperatura=0.1, esfuerzo="ninguno"
    ):
        if fragmento.texto:
            if not trozos:
                ttft = (time.perf_counter() - t_gen) * 1000
            trozos.append(fragmento.texto)

    texto = "".join(trozos).strip().strip('"')

    material = ctx.material()
    hechos = await _cifras_citables(cur, {p.document_id for p in pasajes})
    resultado = evaluar(texto, contexto=material, hechos=hechos, hay_pasajes=bool(pasajes))

    citas = tuple(
        Citation(
            chunk_id=p.chunk_id,
            document=p.documento,
            section=p.section or None,
            snippet=p.contenido[:220],
            score=p.puntuacion,
        )
        for p in pasajes
    )

    if not resultado.aprobada:
        log.info("Sugerencia bloqueada (%s): %s", resultado.bloqueos, resultado.motivo)

    return Sugerencia(
        texto=texto,
        citas=citas,
        guardarrailes=resultado,
        latencia_ms=round((time.perf_counter() - inicio) * 1000, 1),
        ttft_ms=round(ttft, 1),
        modelo=getattr(proveedor, "nombre", "desconocido"),
    )
