"""Tests de la base de conocimiento y la búsqueda híbrida."""

from __future__ import annotations

import os
from pathlib import Path

import psycopg
import pytest
from cea_rag import buscar, extraer, fusionar_rrf, leer_documento, trocear

KB = Path("packages/synthetic-data/src/cea_synthetic/kb")
DSN = os.environ.get("CEA_DATABASE_URL", "postgresql://cea:cea_dev@localhost:5432/cea")


def _hay_indice() -> bool:
    try:
        with psycopg.connect(DSN, connect_timeout=2) as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM kb_chunks WHERE embedding IS NOT NULL")
            return (cur.fetchone() or (0,))[0] > 0
    except Exception:
        return False


# ── troceado ─────────────────────────────────────────────────────────────────


def test_una_tabla_no_se_parte_por_la_mitad() -> None:
    """Es el peor corte posible en un tarifario.

    La mitad de arriba queda con conceptos sin importes y la de abajo con
    importes sin concepto. Cada trozo, por separado, es peor que inútil: puede
    citarse con aparente autoridad diciendo una cifra que no corresponde.
    """
    doc = leer_documento((KB / "tarifario.md").read_text())
    trozos = trocear(doc)

    con_tabla = [t for t in trozos if "| Tarjeta de Crédito Oro |" in t.contenido]
    assert con_tabla, "la tabla de membresías desapareció del índice"
    # Los tres productos tienen que seguir juntos con sus importes.
    tabla = con_tabla[0].contenido
    for producto in ("Clásica", "Oro", "Signature"):
        assert producto in tabla
    assert "45.00" in tabla


def test_cada_trozo_lleva_su_encabezado() -> None:
    """Sin él, "S/ 45.00 anuales" no dice de qué producto habla.

    Ni la búsqueda léxica ni la densa lo encuentran ante una consulta que
    nombre la tarjeta, y citado suelto no sostiene nada.
    """
    doc = leer_documento((KB / "tarifario.md").read_text())

    for t in trocear(doc):
        if t.section:
            assert t.contenido.startswith(t.section)


def test_el_frontmatter_incompleto_falla_al_indexar_no_despues() -> None:
    with pytest.raises(ValueError, match="Faltan metadatos"):
        leer_documento("---\ntitle: Sin identificador\n---\ncuerpo")

    with pytest.raises(ValueError, match="frontmatter"):
        leer_documento("# Documento sin metadatos")


# ── hechos citables ──────────────────────────────────────────────────────────


def test_extrae_las_comisiones_de_la_tabla() -> None:
    """Son las cifras contra las que se verificará lo que diga el modelo."""
    hechos = extraer("tarifario", (KB / "tarifario.md").read_text())
    valores = {h.valor for h in hechos if h.unidad == "pen"}

    assert {25.0, 45.0, 120.0} <= valores, "faltan membresías"
    assert 30.0 in valores, "falta la comisión por pago tardío"
    assert any(h.unidad == "porcentaje" and h.valor == 5.0 for h in hechos)


def test_extrae_el_plazo_legal_escrito_en_palabras() -> None:
    """El procedimiento dice "quince (15) días hábiles", no "15 días"."""
    hechos = extraer("reclamos", (KB / "reclamos.md").read_text())

    plazos = [h for h in hechos if h.unidad == "dias_habiles"]
    assert plazos, "no se extrajo ningún plazo"
    assert any(h.valor == 15.0 for h in plazos)


def test_cada_hecho_conserva_la_frase_de_origen() -> None:
    """Una verificación discutida tiene que poder contrastarse sin abrir el documento."""
    hechos = extraer("tarifario", (KB / "tarifario.md").read_text())

    assert all(h.nota for h in hechos)
    assert all(h.document_id == "tarifario" for h in hechos)


# ── fusión ───────────────────────────────────────────────────────────────────


def test_lo_que_aparece_en_ambas_busquedas_sube() -> None:
    """Es la razón de fusionar: el acuerdo entre dos señales distintas vale más
    que un primer puesto en una sola."""
    puntos = fusionar_rrf(lexica=["a", "b", "c"], densa=["c", "d", "a"])

    assert puntos["a"][1] == "ambas"
    assert puntos["c"][1] == "ambas"
    assert puntos["b"][1] == "lexica"
    # "c" es 3º y 1º; "b" es 2º en una sola lista.
    assert puntos["c"][0] > puntos["b"][0]


def test_se_fusionan_posiciones_y_no_puntuaciones() -> None:
    """La similitud coseno y ts_rank viven en escalas sin relación.

    Sumarlas exigiría calibrar dos distribuciones que además cambian con el
    corpus; la posición es comparable sin calibrar nada.
    """
    solo_lexica = fusionar_rrf(["x"], [])
    solo_densa = fusionar_rrf([], ["x"])

    assert solo_lexica["x"][0] == pytest.approx(solo_densa["x"][0])


# ── búsqueda contra la base indexada ─────────────────────────────────────────

requiere_indice = pytest.mark.skipif(
    not _hay_indice(), reason="Base de conocimiento sin indexar. Ejecutar `make kb`."
)


@requiere_indice
async def test_la_busqueda_lexica_responde_a_preguntas_conversacionales(db_cursor) -> None:
    """websearch_to_tsquery une los términos con AND, y eso la dejaba muerta.

    Medido sobre esta base: "¿Cuánto cobran al año por la tarjeta Oro?" devolvía
    CERO resultados porque ningún trozo contiene a la vez "cuanto", "cobran",
    "año", "por" y "tarjeta". La búsqueda dejaba de ser híbrida sin que nada
    fallara.
    """
    pasajes = await buscar(db_cursor, "¿Cuánto cobran al año por la tarjeta Oro?", None, devolver=3)

    assert pasajes, "el lado léxico no devolvió nada"
    assert all(p.origen == "lexica" for p in pasajes)


@requiere_indice
async def test_encuentra_un_identificador_literal(db_cursor) -> None:
    """Lo que la búsqueda densa pierde: una referencia legal exacta."""
    pasajes = await buscar(db_cursor, "Ley 31763", None, devolver=3)

    assert any("31763" in p.contenido for p in pasajes)
