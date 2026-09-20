"""La clasificación que tiene consecuencia legal.

Clasificar un reclamo como requerimiento priva al usuario del plazo de quince
días hábiles y de la vía de escalamiento a la SBS, y es un incumplimiento. Estas
pruebas no protegen una funcionalidad: protegen que el sistema no empuje al
ejecutivo a cometerlo.
"""

from __future__ import annotations

from cea_contracts import CaseType
from cea_reclamos import Desenlace, Marca, clasificar, extraer


def _clasificar(*textos: str):
    return clasificar(extraer([(f"t{i}", t) for i, t in enumerate(textos)]))


def test_una_afectacion_sin_retirar_es_reclamo() -> None:
    d = _clasificar(
        "Tengo un consumo de mil cuatrocientos cincuenta soles que yo no hice.",
        "Quiero que me devuelvan mi dinero hoy mismo.",
    )
    assert d.desenlace is Desenlace.ABRIR_CASO
    assert d.tipo is CaseType.RECLAMO


def test_la_retractacion_posterior_cierra_sin_caso() -> None:
    """El 61% de las disputas: el cargo resulta ser del propio cliente.

    Abrir un caso por cada una satura la operación y dispara plazos de la Ley
    31763 sin motivo.
    """
    d = _clasificar(
        "Le llamo porque tengo un cargo que no reconozco.",
        "Ah, ya caigo. Ese día fui al aeropuerto. Qué pena, disculpe la molestia.",
    )
    assert d.desenlace is Desenlace.RESUELTO_EN_LLAMADA
    assert d.tipo is None


def test_una_retractacion_ANTERIOR_no_retira_la_queja_que_vino_despues() -> None:
    """El orden es lo que le da sentido, y compararlo sólo por presencia falla.

    El cliente reconoce un cargo y acto seguido disputa OTRO. Tratar las dos
    marcas como un conjunto sin orden cerraría la llamada sin caso y dejaría al
    usuario sin su reclamo: exactamente el incumplimiento.
    """
    d = _clasificar(
        "Ah, ya caigo, ese consumo de Rappi sí era mío, disculpe.",
        "Pero hay otro de mil soles en AliExpress que yo no hice.",
    )
    assert d.desenlace is Desenlace.ABRIR_CASO
    assert d.tipo is CaseType.RECLAMO


def test_pedir_el_libro_de_reclamaciones_gana_a_todo() -> None:
    """El usuario está ejerciendo un derecho; negárselo es el incumplimiento."""
    d = _clasificar(
        "Ya entendí la explicación y tiene razón,",
        "pero igual quiero que me den el Libro de Reclamaciones.",
    )
    assert d.desenlace is Desenlace.ABRIR_CASO
    assert d.tipo is CaseType.RECLAMO


def test_mencionar_a_la_sbs_es_reclamo_aunque_no_haya_queja_explicita() -> None:
    d = _clasificar("Si no me responden voy a ir a la SBS.")
    assert d.tipo is CaseType.RECLAMO
    assert d.confianza >= 0.9


def test_una_gestion_sin_afectacion_es_requerimiento() -> None:
    d = _clasificar(
        "Buenos días, quiero consultar cómo va mi trámite.",
        "¿Me puede enviar una copia del contrato?",
    )
    assert d.desenlace is Desenlace.ABRIR_CASO
    assert d.tipo is CaseType.REQUERIMIENTO


def test_una_gestion_CON_afectacion_es_reclamo_no_requerimiento() -> None:
    """El caso que más se clasifica mal bajo presión de tiempo.

    El cliente pide un documento —parece una gestión— pero lo pide porque le
    cobraron algo que no reconoce. Manda la afectación.
    """
    d = _clasificar(
        "Me cobraron una comisión que no reconozco,",
        "¿me puede enviar una copia del estado de cuenta para revisarlo?",
    )
    assert d.tipo is CaseType.RECLAMO


def test_sin_materia_no_se_inventa_un_caso() -> None:
    d = _clasificar(
        "Buenos días, le llamo para saludar.",
        "Nada más, muchas gracias.",
    )
    assert d.desenlace is Desenlace.SIN_MATERIA
    assert d.tipo is None


def test_ninguna_confianza_llega_a_uno() -> None:
    """Una confianza de 1.0 invita a confirmar sin leer.

    Y el ejecutivo CONFIRMA la clasificación: ese automatismo es justamente lo
    que este control existe para evitar.
    """
    casos = [
        _clasificar("Quiero poner un reclamo formal."),
        _clasificar("Me han robado, yo no hice ese consumo."),
        _clasificar("Quiero consultar el estado de mi trámite."),
    ]
    assert all(0.0 < d.confianza < 1.0 for d in casos)


def test_la_evidencia_decisiva_va_primero() -> None:
    """El ejecutivo contrasta el veredicto leyendo la primera línea.

    En una retractación, la queja la precede en tres frases; ordenar todo por
    orden cronológico dejaría el motivo del veredicto al final.
    """
    d = _clasificar(
        "Tengo un cargo que no reconozco.",
        "Yo nunca he comprado ahí.",
        "Ah, ya caigo, disculpe la molestia.",
    )
    assert d.desenlace is Desenlace.RESUELTO_EN_LLAMADA
    assert "caigo" in d.evidencia[0] or "molestia" in d.evidencia[0]


def test_la_evidencia_apunta_a_turnos_reales() -> None:
    """Sin los turnos, el ejecutivo no puede ir a mirar de dónde salió."""
    d = _clasificar("Buenos días.", "Me cobraron dos veces la misma compra.")
    assert d.turnos_de_evidencia == ("t1",)


def test_la_negacion_no_se_pierde_al_normalizar() -> None:
    """«no reconozco» no puede convertirse en «reconozco».

    El normalizador de los guardarraíles del copiloto elimina palabras vacías y
    «no» está entre ellas; reutilizarlo aquí invertiría el sentido de la mitad
    de las señales.
    """
    from cea_reclamos.senales import normalizar

    assert "no" in normalizar("No reconozco este cargo").split()
    assert _clasificar("No reconozco este cargo").tipo is CaseType.RECLAMO


def test_solo_entran_turnos_del_cliente() -> None:
    """Lo que dice el ejecutivo no es evidencia de lo que reclama el cliente.

    Si el clasificador se apoyara en «vamos a registrar un reclamo formal», no
    haría más que repetirle al ejecutivo lo que acaba de decidir, y sería ciego
    al caso que existe para evitar: que NO lo registre.
    """
    senales = extraer([("t1", "Buenos días, ¿en qué le ayudo?")])
    assert not senales.tiene(Marca.AFECTACION)
