"""Troceado de documentos de la base de conocimiento.

El troceado decide el techo de calidad de todo el RAG: se puede tener el mejor
buscador y el mejor modelo, pero si el trozo recuperado parte una tabla de
comisiones por la mitad, la respuesta citará una cifra sin su concepto.

Por eso se trocea respetando la estructura del documento —encabezados, tablas,
listas— y no cada N caracteres.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import yaml

# Tamaño objetivo en palabras.
#
# El plan habla de 200-300 tokens con 50 de solapamiento. En español un token
# ronda 0.75 palabras, así que 200 palabras caen dentro de ese rango. Se cuenta
# en palabras y no en tokens para no atar el troceado al tokenizador de un
# modelo concreto: cambiarlo obligaría a reindexar todo.
OBJETIVO_PALABRAS = 200
SOLAPE_PALABRAS = 40

# Un trozo por debajo de esto casi nunca aporta contexto suficiente para
# sostener una afirmación, y ensucia los resultados de búsqueda.
MINIMO_PALABRAS = 25

_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)
_ENCABEZADO = re.compile(r"^(#{1,6})\s+(.*)$", re.M)


@dataclass(slots=True, frozen=True)
class Documento:
    document_id: str
    title: str
    kind: str
    version: str
    effective_from: str
    cuerpo: str


@dataclass(slots=True, frozen=True)
class Trozo:
    chunk_id: str
    document_id: str
    section: str
    ordinal: int
    contenido: str

    @property
    def palabras(self) -> int:
        return len(self.contenido.split())


def leer_documento(texto: str) -> Documento:
    """Separa el frontmatter YAML del cuerpo en Markdown."""
    m = _FRONTMATTER.match(texto)
    if not m:
        raise ValueError("El documento no tiene frontmatter YAML con sus metadatos.")
    meta = yaml.safe_load(m.group(1))
    faltan = {"document_id", "title", "kind", "version", "effective_from"} - set(meta)
    if faltan:
        raise ValueError(f"Faltan metadatos en el frontmatter: {', '.join(sorted(faltan))}")
    return Documento(
        document_id=str(meta["document_id"]),
        title=str(meta["title"]),
        kind=str(meta["kind"]),
        version=str(meta["version"]),
        effective_from=str(meta["effective_from"]),
        cuerpo=texto[m.end() :].strip(),
    )


def _secciones(cuerpo: str) -> list[tuple[str, str]]:
    """Parte el cuerpo por encabezados, conservando el título de cada sección."""
    encabezados = list(_ENCABEZADO.finditer(cuerpo))
    if not encabezados:
        return [("", cuerpo)]

    salida: list[tuple[str, str]] = []
    preambulo = cuerpo[: encabezados[0].start()].strip()
    if preambulo:
        salida.append(("", preambulo))

    for i, m in enumerate(encabezados):
        fin = encabezados[i + 1].start() if i + 1 < len(encabezados) else len(cuerpo)
        titulo = m.group(2).strip()
        contenido = cuerpo[m.end() : fin].strip()
        if contenido:
            salida.append((titulo, contenido))
    return salida


def _es_tabla(bloque: str) -> bool:
    lineas = bloque.strip().splitlines()
    return len(lineas) >= 2 and lineas[0].strip().startswith("|")


def _partir_seccion(contenido: str) -> list[str]:
    """Parte una sección larga en trozos, sin romper tablas ni listas.

    Una tabla de comisiones partida por la mitad produce un trozo con conceptos
    sin importes y otro con importes sin concepto: cada uno, por separado, es
    peor que inútil, porque puede citarse con aparente autoridad.
    """
    bloques = [b.strip() for b in re.split(r"\n\s*\n", contenido) if b.strip()]
    trozos: list[str] = []
    actual: list[str] = []
    palabras = 0

    for bloque in bloques:
        n = len(bloque.split())
        # Una tabla viaja entera aunque se pase del objetivo.
        if _es_tabla(bloque) and actual and palabras + n > OBJETIVO_PALABRAS:
            trozos.append("\n\n".join(actual))
            actual, palabras = [bloque], n
            continue

        if palabras + n > OBJETIVO_PALABRAS and actual:
            trozos.append("\n\n".join(actual))
            # Solapamiento: se arrastra el último bloque para que una frase a
            # caballo entre dos trozos aparezca completa al menos en uno.
            ultimo = actual[-1]
            if len(ultimo.split()) <= SOLAPE_PALABRAS and not _es_tabla(ultimo):
                actual, palabras = [ultimo, bloque], len(ultimo.split()) + n
            else:
                actual, palabras = [bloque], n
            continue

        actual.append(bloque)
        palabras += n

    if actual:
        trozos.append("\n\n".join(actual))
    return trozos


def trocear(doc: Documento) -> list[Trozo]:
    """Convierte un documento en trozos indexables."""
    trozos: list[Trozo] = []
    for titulo, contenido in _secciones(doc.cuerpo):
        for parte in _partir_seccion(contenido):
            if len(parte.split()) < MINIMO_PALABRAS and trozos and not _es_tabla(parte):
                # Un resto corto se pega al trozo anterior en lugar de quedar
                # suelto: aislado no sostiene nada, pero como cola del anterior
                # aporta contexto.
                previo = trozos.pop()
                trozos.append(
                    Trozo(
                        previo.chunk_id,
                        previo.document_id,
                        previo.section,
                        previo.ordinal,
                        previo.contenido + "\n\n" + parte,
                    )
                )
                continue

            ordinal = len(trozos)
            # El encabezado se antepone al texto indexado.
            #
            # Sin él, un trozo que dice "S/ 45.00 anuales" no menciona de qué
            # producto habla, y tanto la búsqueda léxica como la densa lo
            # pierden ante una consulta que nombre la tarjeta.
            cuerpo = f"{titulo}\n\n{parte}" if titulo else parte
            trozos.append(
                Trozo(
                    chunk_id=f"{doc.document_id}#{ordinal:03d}",
                    document_id=doc.document_id,
                    section=titulo,
                    ordinal=ordinal,
                    contenido=cuerpo.strip(),
                )
            )
    return trozos
