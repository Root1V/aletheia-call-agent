"""Generación de la sugerencia, de extremo a extremo."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from cea_contracts import Citation
from cea_llm import ProveedorLLM
from cea_rag import Pasaje, Reordenador, buscar

from .atribucion import atribuir
from .guardarrailes import Resultado, evaluar
from .prompt import Contexto, construir

log = logging.getLogger("cea.copilot")

# Cuántos pasajes se le entregan al modelo.
#
# Cinco es el equilibrio: con menos se queda sin material para preguntas que
# cruzan dos documentos, y con más el modelo empieza a mezclar procedimientos
# distintos en la misma frase. Se recuperan treinta candidatos y se recortan
# tras fusionar.
#
# El número tiene un precio medido, y no el que yo creía. Cada pasaje añade
# ~210 ms al primer token, porque son ~300 tokens más de prefill y los pasajes
# CAMBIAN en cada sugerencia, así que no los cubre la caché de prefijo del
# despliegue:
#
#     1 pasaje ....  325 ms      3 pasajes ....  729 ms
#     2 pasajes ...  561 ms      5 pasajes .... 1166 ms
#
# Una medición anterior decía que el primer token era plano entre dos y ocho
# pasajes. Era falsa: repetía el MISMO prompt, y lo que medía era la caché.
#
# Se mantienen cinco porque con el reordenador la cobertura del pasaje correcto
# sube al 100% (13/13) frente al 92% con tres. Un pasaje que falta no produce
# una respuesta mala —los guardarraíles la bloquean— sino ninguna respuesta, y
# el silencio es lo que hace que el ejecutivo deje de mirar el panel.
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
    recuperacion_ms: float
    """Lo que costó recuperar y reordenar, aparte de la generación.

    Va separado porque son dos presupuestos distintos con dos palancas
    distintas: la recuperación se ajusta con la profundidad del reordenador, la
    generación con el modelo y el largo de la respuesta. Un total que sube sin
    decir cuál de los dos creció no se puede accionar."""
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
    reordenador: Reordenador | None = None,
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
        await buscar(
            cur,
            consulta,
            vector,
            candidatos=CANDIDATOS,
            devolver=PASAJES,
            reordenador=reordenador,
        )
    )

    recuperacion_ms = (time.perf_counter() - inicio) * 1000

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

    # Se citan los pasajes que APORTARON a la frase, no los cinco recuperados.
    # Una frase construida sólo con los datos de la llamada no lleva cita, y eso
    # es correcto: el portal lo muestra como lo que es.
    citas = tuple(
        Citation(
            chunk_id=p.chunk_id,
            document=p.documento,
            section=p.section or None,
            snippet=p.contenido[:220],
            score=p.puntuacion,
        )
        for p in atribuir(texto, pasajes, datos_de_la_llamada=datos_de_la_llamada)
    )

    if not resultado.aprobada:
        log.info("Sugerencia bloqueada (%s): %s", resultado.bloqueos, resultado.motivo)

    return Sugerencia(
        texto=texto,
        citas=citas,
        guardarrailes=resultado,
        latencia_ms=round((time.perf_counter() - inicio) * 1000, 1),
        recuperacion_ms=round(recuperacion_ms, 1),
        ttft_ms=round(ttft, 1),
        modelo=getattr(proveedor, "nombre", "desconocido"),
    )
