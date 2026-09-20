"""El contexto de la llamada, reducido a lo que el modelo puede usar.

Esta es la frontera entre el workspace y el prompt, y no es una serialización:
es una decisión sobre qué puede afirmar el copiloto. Todo lo que entra aquí es
citable; todo lo que no entra, el modelo no lo puede mencionar y los
guardarraíles lo bloquearán si lo intenta.

Por eso se deja fuera a propósito material que sí está en el panel:

- El nombre completo, el documento y el teléfono del cliente. El ejecutivo los
  tiene delante y el modelo no los necesita para redactar; incluirlos sólo crea
  la ocasión de que los repita en voz alta sin que nadie se lo haya pedido.
- El riesgo de fraude y el nivel de verificación. Son para decidir, no para
  decir: "su riesgo de fraude es bajo" es una frase que ningún banco quiere que
  se pronuncie por teléfono.
- Los saldos y el 360 completo. Fuera del alcance de una sugerencia de reclamo.
"""

from __future__ import annotations

from cea_contracts import CallContext, Transaction, fmt_fecha_hora

# Cuántas transacciones de apoyo se describen una a una.
#
# Más allá de tres, el modelo empieza a enumerarlas en la respuesta en lugar de
# resumirlas, y una frase de 40 palabras no aguanta una lista. El resto se
# entrega como recuento, que es como se dice por teléfono: "ha comprado ahí seis
# veces", no "el 3, el 11, el 19 y el 24 de agosto".
APOYO_DETALLADO = 3


def _describir(t: Transaction, *, etiqueta: str) -> str:
    # El descriptor crudo va SIEMPRE, junto al comercio resuelto.
    #
    # Es el puente entero del producto: el cliente está mirando "SUNRISE TECH"
    # en su estado de cuenta y el panel dice "inDrive". Si el material le da al
    # modelo sólo el nombre resuelto, la sugerencia nombra un comercio que el
    # cliente no ve por ninguna parte y la llamada empeora en vez de cerrarse.
    # "S/" y no "PEN": es lo que el cliente ve en su estado de cuenta y lo que
    # el ejecutivo dice en voz alta, así que es también como el modelo redacta.
    moneda = "S/" if t.currency == "PEN" else t.currency
    partes = [f"{etiqueta}: {moneda} {t.amount}"]
    if t.merchant:
        partes.append(f"comercio real {t.merchant.display_name}")
        partes.append(f"que el cliente ve en su estado de cuenta como «{t.raw_descriptor}»")
    else:
        partes.append(
            f"descriptor en el estado de cuenta «{t.raw_descriptor}», comercio sin resolver"
        )
    partes += [
        fmt_fecha_hora(t.occurred_at),
        f"canal {t.channel.value}",
        f"estado {t.status.value}",
    ]
    if t.device_label:
        partes.append(f"dispositivo {t.device_label}")
    if t.decline_reason:
        partes.append(f"motivo del rechazo: {t.decline_reason}")
    if t.is_recurring:
        partes.append("cargo recurrente")
    return " · ".join(partes)


def resumir(ctx: CallContext) -> str:
    """Los hechos de esta llamada, en texto plano y verificables uno a uno.

    Va en texto y no en JSON porque el modelo redacta sobre esto: con JSON
    tiende a devolver JSON, y lo que hace falta es una frase para decir en voz
    alta.
    """
    lineas: list[str] = [
        f"Motivo probable de la llamada: {ctx.intent.intent.value} "
        f"(confianza {ctx.intent.confidence:.2f})."
    ]
    lineas.extend(f"Indicio: {e}" for e in ctx.intent.evidence)

    por_id = {t.transaction_id: t for t in ctx.relevant_transactions}

    foco = por_id.get(ctx.focus_transaction_id or "")
    if foco is not None:
        lineas.append(_describir(foco, etiqueta="Cargo en discusión"))
        if foco.prior_purchases_90d:
            lineas.append(
                f"El cliente tiene {foco.prior_purchases_90d} compras previas en ese "
                "comercio en los últimos 90 días."
            )

    apoyo = [por_id[i] for i in ctx.supporting_transaction_ids if i in por_id]
    for t in apoyo[:APOYO_DETALLADO]:
        lineas.append(_describir(t, etiqueta="Compra anterior en el mismo comercio"))
    if len(apoyo) > APOYO_DETALLADO:
        lineas.append(
            f"Y {len(apoyo) - APOYO_DETALLADO} compras anteriores más en el mismo comercio."
        )

    # Los reintentos posteriores NO se mezclan con las compras previas.
    #
    # Significan lo contrario: un cliente que compró no reintenta el mismo monto
    # tras un rechazo. Presentarlos juntos le permitiría al modelo escribir
    # "usted ha comprado ahí nueve veces" en un caso de fraude.
    reintentos = [por_id[i] for i in ctx.related_attempt_ids if i in por_id]
    if reintentos:
        lineas.append(
            f"Además hay {len(reintentos)} intentos POSTERIORES en el mismo comercio, "
            "que no son compras del cliente sino reintentos."
        )

    # Los eventos de la cuenta que se refieren al cargo en discusión se omiten:
    # ya está descrito arriba, con más detalle y con su descriptor. Repetirlo
    # con otras palabras le sugiere al modelo que son dos cargos distintos.
    for ev in ctx.recent_account_events[:4]:
        if ev.related_transaction_id and ev.related_transaction_id == ctx.focus_transaction_id:
            continue
        lineas.append(
            f"Evento reciente de la cuenta: {ev.summary} ({fmt_fecha_hora(ev.occurred_at)})."
        )

    for caso in ctx.open_cases:
        lineas.append(
            f"Caso abierto {caso.folio} ({caso.case_type.value}, {caso.status.value}): "
            f"{caso.subject}. Plazo de respuesta hasta el {fmt_fecha_hora(caso.due_at)}."
        )

    lineas.extend(_journey(ctx))

    return "\n".join(f"- {linea}" for linea in lineas)


def _journey(ctx: CallContext) -> list[str]:
    """El intento fallido en la app, agrupado en vez de repetido.

    Tres líneas idénticas de "el formulario no avanzó del paso 2" no son tres
    hechos: son un hecho con una intensidad. Enumeradas, el modelo las trata
    como eventos distintos y las lista; agrupadas, dicen lo que importa —que el
    cliente ya lo intentó tres veces y por eso está llamando— en una sola frase
    que cabe en la respuesta.
    """
    grupos: dict[tuple, list] = {}
    for j in ctx.digital_journey:
        grupos.setdefault((j.channel, j.screen, j.action, j.succeeded, j.detail), []).append(j)

    lineas: list[str] = []
    for (canal, pantalla, accion, logrado, detalle), eventos in list(grupos.items())[:4]:
        veces = "" if len(eventos) == 1 else f" {len(eventos)} veces"
        desenlace = "y lo logró" if logrado else "sin conseguirlo"
        cola = f" ({detalle})" if detalle else ""
        ultimo = max(e.occurred_at for e in eventos)
        lineas.append(
            f"Antes de llamar, por {canal.value} en «{pantalla}» intentó {accion}{veces} "
            f"{desenlace}{cola}; la última vez {fmt_fecha_hora(ultimo)}."
        )
    return lineas
