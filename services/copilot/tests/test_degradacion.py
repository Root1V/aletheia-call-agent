"""Sin vector, el copiloto sigue contestando.

Esta prueba existe por un compromiso con otro equipo, no por prolijidad. El
equipo de plataforma dimensionó nuestro presupuesto de peticiones sobre una
frase nuestra —«quedarnos sin la bolsa de embeddings nos deja sin vector y sin
reordenador, pero la sugerencia sale igual»— y nos pidió expresamente avisar si
alguna vez deja de ser cierta, porque su decisión de capacidad cuelga de ahí.

Un compromiso que sólo vive en un hilo de conversación se rompe el día que
alguien hace que la búsqueda densa sea obligatoria, sin enterarse de que acaba
de invalidar el dimensionamiento de otro equipo. Por eso está aquí: si esto se
pone rojo, hay que escribir en el canal antes de arreglarlo.

Las tres bolsas —`embeddings`, `rerank` y `chat_completions`— tienen presupuesto
propio desde el 19/09, así que agotar una no toca a las otras: es exactamente el
caso que se prueba.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import psycopg
import pytest
from cea_copilot import generar
from cea_llm import Fragmento

DSN = os.environ.get("CEA_DATABASE_URL", "postgresql://cea:cea_dev@localhost:5432/cea")

CONSULTA = "cuánto cuesta la membresía anual de la tarjeta oro"
RESPUESTA = "La membresía anual de la Tarjeta Oro es de S/ 45.00, cobrada en el mes de aniversario."


def _hay_indice() -> bool:
    try:
        with psycopg.connect(DSN, connect_timeout=2) as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM kb_chunks")
            return (cur.fetchone() or (0,))[0] > 0
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _hay_indice(), reason="Sin base de conocimiento indexada. Ejecutar `make kb`."
)


@dataclass
class ProveedorFijo:
    """Devuelve siempre lo mismo.

    El modelo no es lo que se prueba: lo que se prueba es que la recuperación y
    la verificación funcionan sin vector. Llamar a la plataforma aquí ataría
    esta prueba a su disponibilidad y a su cupo, que es justo lo que la prueba
    existe para sobrevivir.
    """

    texto: str = RESPUESTA
    nombre: str = "fijo"
    prompts: list = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.prompts = []

    async def transmitir(self, mensajes, **_kw):
        self.prompts.append(mensajes)
        for palabra in self.texto.split(" "):
            yield Fragmento(texto=palabra + " ")


async def test_sin_vector_la_sugerencia_sale_igual() -> None:
    """El compromiso, comprobado de extremo a extremo."""
    proveedor = ProveedorFijo()
    async with (
        await psycopg.AsyncConnection.connect(DSN, row_factory=psycopg.rows.dict_row) as conn,
        conn.cursor() as cur,
    ):
        sugerencia = await generar(
            cur,
            proveedor,
            turno_del_cliente="¿Cuánto me cobran al año por la tarjeta oro?",
            datos_de_la_llamada="",
            consulta_kb=CONSULTA,
            vector=None,  # la bolsa de embeddings agotada
        )

    assert sugerencia.citas, "sin vector no se recuperó nada citable"
    assert sugerencia.mostrable, f"bloqueada sin vector: {sugerencia.guardarrailes.motivo}"
    assert "45.00" in sugerencia.texto


async def test_sin_vector_el_pasaje_correcto_sigue_llegando_al_modelo() -> None:
    """Que conteste no basta: tiene que conteste con el material correcto.

    Si la búsqueda léxica dejara de encontrar el tarifario, la sugerencia se
    bloquearía por falta de respaldo en lugar de degradarse, y eso SÍ sería una
    caída desde el punto de vista de quien dimensiona.
    """
    proveedor = ProveedorFijo()
    async with (
        await psycopg.AsyncConnection.connect(DSN, row_factory=psycopg.rows.dict_row) as conn,
        conn.cursor() as cur,
    ):
        await generar(
            cur,
            proveedor,
            turno_del_cliente="¿Cuánto me cobran al año por la tarjeta oro?",
            datos_de_la_llamada="",
            consulta_kb=CONSULTA,
            vector=None,
        )

    material = "\n".join(m.contenido for m in proveedor.prompts[0])
    assert "membresía" in material.lower()
    assert "45.00" in material


async def test_sin_vector_y_sin_reordenador_tampoco_se_cae() -> None:
    """Las dos pérdidas a la vez: es lo que ocurre cuando se agota esa bolsa.

    Antes del 19/09 `embeddings` y `rerank` compartían presupuesto, así que
    perder uno era perder los dos. Hoy tienen bolsas separadas y el caso es menos
    probable, pero sigue siendo el peor escenario y tiene que aguantar.
    """
    proveedor = ProveedorFijo()
    async with (
        await psycopg.AsyncConnection.connect(DSN, row_factory=psycopg.rows.dict_row) as conn,
        conn.cursor() as cur,
    ):
        sugerencia = await generar(
            cur,
            proveedor,
            turno_del_cliente="¿Cuánto me cobran al año por la tarjeta oro?",
            datos_de_la_llamada="",
            consulta_kb=CONSULTA,
            vector=None,
            reordenador=None,
        )

    assert sugerencia.mostrable
    assert sugerencia.citas
