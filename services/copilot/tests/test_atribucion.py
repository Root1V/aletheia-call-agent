"""Una cita tiene que respaldar la frase, no acompañarla.

Citar el primer pasaje recuperado es lo cómodo y es lo que hay que evitar: en
el flujo de reclamos la mayoría de las frases se construyen enteras con los
datos de la llamada, y ponerles debajo una referencia al tarifario le dice al
ejecutivo que hay respaldo documental donde no lo hay. Es él quien responde si
el cliente pregunta de dónde sale el dato.
"""

from __future__ import annotations

from cea_copilot import atribuir
from cea_rag import Pasaje


def _pasaje(chunk_id: str, contenido: str, section: str = "") -> Pasaje:
    return Pasaje(
        chunk_id=chunk_id,
        document_id=chunk_id.split("#")[0],
        documento="Documento de prueba",
        section=section,
        contenido=contenido,
        puntuacion=1.0,
        origen="lexica",
    )


TARIFARIO = _pasaje(
    "tarifario#000",
    "La comisión de membresía anual de la Tarjeta Oro es de S/ 45.00 y se cobra "
    "en el mes de aniversario de la tarjeta, el mismo mes en que fue activada.",
    "Membresía anual",
)
DESCRIPTORES = _pasaje(
    "proc#000",
    "El texto que aparece en el estado de cuenta lo define el procesador de pagos "
    "del comercio y no el banco, por eso el descriptor puede diferir del nombre "
    "comercial que el cliente conoce.",
    "Descriptores del estado de cuenta",
)
REPOSICION = _pasaje(
    "tarifario#002",
    "La reposición del plástico por deterioro, pérdida o robo cuesta S/ 20.00. "
    "La primera reposición del año es gratuita cuando el motivo es robo.",
    "Reposición de plástico",
)


def test_cita_el_pasaje_del_que_sale_la_respuesta() -> None:
    frase = (
        "La comisión de membresía anual de la Tarjeta Oro es de S/ 45.00, "
        "cobrada en el mes de aniversario."
    )
    citas = atribuir(frase, (REPOSICION, TARIFARIO, DESCRIPTORES))
    assert citas
    assert citas[0].chunk_id == "tarifario#000"


def test_una_frase_hecha_solo_con_datos_de_la_llamada_no_lleva_cita() -> None:
    """El caso más frecuente del flujo de reclamos, y el que más se falsea.

    El comercio real, la fecha y las compras previas salen del contexto de la
    llamada, no de ningún documento. Sin este control, la tarjeta mostraría
    debajo la referencia al tarifario que encabezaba la búsqueda.
    """
    frase = (
        "El cargo de S/ 189.90 del 16/09 corresponde al comercio inDrive, donde "
        "usted ya realizó 6 compras previas en los últimos 90 días."
    )
    assert atribuir(frase, (TARIFARIO, REPOSICION)) == ()


def test_el_vocabulario_bancario_compartido_no_basta_para_citar() -> None:
    """«tarjeta», «cliente» y «comercio» están en todos los documentos.

    Si el solapamiento casual bastara, toda frase citaría todo, que es
    exactamente el problema que esto resuelve.
    """
    frase = "Permítame revisar el consumo de su tarjeta y le confirmo en un momento."
    assert atribuir(frase, (TARIFARIO, REPOSICION)) == ()


def test_no_devuelve_mas_de_dos_citas() -> None:
    """El ejecutivo no abre cinco documentos con el cliente al teléfono."""
    frase = (
        "La comisión de membresía anual de la Tarjeta Oro es de S/ 45.00 y la "
        "reposición del plástico por pérdida o robo cuesta S/ 20.00, y el "
        "descriptor del estado de cuenta lo define el procesador de pagos."
    )
    assert len(atribuir(frase, (TARIFARIO, REPOSICION, DESCRIPTORES))) <= 2


def test_una_sugerencia_vacia_no_cita_nada() -> None:
    assert atribuir("", (TARIFARIO,)) == ()
    assert atribuir("   ", (TARIFARIO,)) == ()


DATOS = (
    "- Cargo en discusión: PEN 189.90 · comercio real inDrive · que el cliente ve en "
    "su estado de cuenta como «SUNRISE TECH» · 16/09 10:44 · canal app · estado liquidada\n"
    "- El cliente tiene 6 compras previas en ese comercio en los últimos 90 días."
)


def test_lo_que_ya_estaba_en_la_llamada_no_prueba_que_se_usara_un_documento() -> None:
    """El caso que se coló en la llamada real antes de este descuento.

    La frase se construye entera con el cargo, el comercio y las compras previas
    —todo del contexto— y aun así compartía con el tarifario suficientes
    palabras corrientes ("cargo", "comercio", "cuenta", "mes") como para que se
    le atribuyera la sección de Membresía anual. El ejecutivo habría visto una
    referencia al tarifario bajo una frase que no debe nada al tarifario.
    """
    frase = (
        "El cargo de S/ 189.90 en SUNRISE TECH del 16/09 a las 10:44 corresponde al "
        "comercio inDrive, con 6 compras previas en el mismo comercio."
    )
    assert atribuir(frase, (TARIFARIO, DESCRIPTORES), datos_de_la_llamada=DATOS) == ()


def test_el_descuento_no_se_lleva_por_delante_una_cita_legitima() -> None:
    """Descontar el contexto no puede dejar sin fuente a lo que sí la tiene.

    La cifra del tarifario no aparece por ninguna parte en los datos de la
    llamada, así que sigue siendo atribuible aunque la frase mencione la tarjeta.
    """
    frase = (
        "La comisión de membresía anual de la Tarjeta Oro es de S/ 45.00, cobrada "
        "en el mes de aniversario de la tarjeta."
    )
    citas = atribuir(frase, (DESCRIPTORES, TARIFARIO, REPOSICION), datos_de_la_llamada=DATOS)
    assert citas and citas[0].chunk_id == "tarifario#000"
