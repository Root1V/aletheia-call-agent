"""Predicción del motivo de la llamada.

Reglas explícitas sobre eventos de cuenta, journey digital y casos abiertos.
No es un LLM ni un modelo entrenado, y eso es deliberado en esta fase:

- Tiene que responder ANTES de descolgar, en pocos milisegundos.
- Cada predicción debe venir con su evidencia legible; sin ella el ejecutivo
  deja de mirar el panel en una semana.
- Entrenar un clasificador exige etiquetas de llamadas reales, que todavía no
  existen. Las reglas producen esas etiquetas: cada predicción confirmada o
  corregida por el ejecutivo es una muestra. Cuando haya volumen, el
  clasificador reemplaza a las reglas detrás de la misma interfaz.

El diseño mantiene la confianza por debajo de 1.0 a propósito: una predicción
que se declara segura y falla cuesta más credibilidad que una prudente.
"""

from __future__ import annotations

from dataclasses import dataclass

from cea_contracts import CallIntent, IntentPrediction, fmt_fecha, fmt_fecha_hora


@dataclass(slots=True)
class Señales:
    """Lo que se sabe del cliente justo antes de descolgar."""

    account_events: list[dict]
    journey: list[dict]
    open_cases: list[dict]
    focus_transaction: dict | None
    duplicates: list[dict] | None = None
    """Pares de cargos idénticos detectados en la cuenta.

    Se calcula con una consulta, no con un modelo: dos cargos del mismo monto
    en el mismo comercio con minutos de diferencia es una comparación
    aritmética. Someter esto a un clasificador sería pagar latencia e
    incertidumbre por algo que tiene respuesta exacta.
    """


# Mapa de eventos de cuenta al motivo que suelen provocar. El orden importa:
# la primera coincidencia gana, así que lo más específico va primero.
_POR_EVENTO: tuple[tuple[str, CallIntent], ...] = (
    ("cargo_rechazado", CallIntent.TARJETA_RECHAZADA),
    ("tarjeta_bloqueada", CallIntent.TARJETA_BLOQUEADA),
    ("transferencia_fallida", CallIntent.CONSULTA_MOVIMIENTO),
    ("cuota_vencida", CallIntent.CONSULTA_SALDO),
)

# Opción del IVR -> motivos que vota, con su peso.
#
# La opción 2 ("reportar un consumo no reconocido") reparte su voto entre la
# disputa por incomprensión y el fraude a propósito: DESDE EL LADO DEL CLIENTE
# las dos son lo mismo, "hay un cargo que no reconozco". Quien las distingue es
# el banco, con evidencia que el cliente no tiene: si hubo compras previas en
# ese comercio, si el consumo salió de su propio dispositivo, si el monitoreo
# de fraude lo marcó. Hacer que el IVR vote sólo por una de las dos fuerza la
# conclusión antes de mirar esa evidencia.
_POR_IVR: dict[str, tuple[tuple[CallIntent, float], ...]] = {
    "IVR:1": ((CallIntent.CONSULTA_SALDO, 2.5),),
    "IVR:2": (
        (CallIntent.DISPUTA_CARGO_NO_RECONOCIDO, 1.3),
        (CallIntent.DISPUTA_FRAUDE, 1.2),
    ),
    "IVR:3": ((CallIntent.TARJETA_BLOQUEADA, 2.5),),
    "IVR:4": ((CallIntent.CONSULTA_PRODUCTO, 2.5),),
}

# Pantallas de la app que, al fallar, anticipan el motivo de la llamada.
_POR_PANTALLA: dict[str, CallIntent] = {
    "reportar_consumo": CallIntent.DISPUTA_CARGO_NO_RECONOCIDO,
    "ayuda_disputas": CallIntent.DISPUTA_CARGO_NO_RECONOCIDO,
    "bloquear_tarjeta": CallIntent.TARJETA_BLOQUEADA,
    "limites_compra": CallIntent.TARJETA_RECHAZADA,
    "estado_cuenta": CallIntent.SEGUIMIENTO_RECLAMO,
}


def predecir(señales: Señales) -> IntentPrediction:
    """Devuelve el motivo más probable con su evidencia."""
    votos: dict[CallIntent, float] = {}
    evidencia: list[str] = []

    def votar(intent: CallIntent, peso: float) -> None:
        votos[intent] = votos.get(intent, 0.0) + peso

    # 1. Un caso abierto domina: quien tiene un reclamo en curso suele llamar
    #    por él, y además hay un plazo regulatorio corriendo.
    for caso in señales.open_cases:
        votar(CallIntent.SEGUIMIENTO_RECLAMO, 3.0)
        evidencia.append(f"Caso abierto {caso['folio']}, vence {fmt_fecha(caso['due_at'])}")
        break

    # 2. Cargos duplicados.
    #
    # Esto NO es un voto más: es una determinación. Dos cargos del mismo monto
    # en el mismo comercio con minutos de diferencia no son "indicio de"
    # duplicado, SON un duplicado, verificado con aritmética exacta.
    #
    # Dejarlo compitiendo por mayoría contra señales circunstanciales —que el
    # cliente marcara la opción 2 del IVR, que fallara un formulario en la app—
    # hace que la suma de tres corazonadas tumbe a un hecho comprobado. Cuando
    # hay evidencia exacta, el resto sólo puede matizar la confianza, no
    # cambiar la conclusión.
    duplicado = (señales.duplicates or [None])[0]
    if duplicado is not None:
        evidencia.insert(
            0,
            f"Dos cargos de S/ {duplicado['amount']} en {duplicado['merchant']} "
            f"con {duplicado['minutos']} minutos de diferencia",
        )
        transacciones_del_duplicado = {duplicado["primero"], duplicado["segundo"]}
    else:
        transacciones_del_duplicado = set()

    # 3. Eventos recientes de la cuenta.
    rechazos_seguidos = 0
    for ev in señales.account_events[:3]:
        for kind, intent in _POR_EVENTO:
            if ev["kind"] == kind:
                votar(intent, 2.0)
                if kind == "cargo_rechazado":
                    rechazos_seguidos += 1
                break
        else:
            if ev["kind"] == "cobro_inusual":
                if ev["related_transaction_id"] in transacciones_del_duplicado:
                    # El duplicado ya explica este evento. Dejar que además vote
                    # por "no reconocido" sería contar la misma evidencia dos
                    # veces, a favor de la conclusión equivocada.
                    pass
                elif ev["severity"] in ("alto", "critico"):
                    # La severidad la asigna el monitoreo de fraude del propio
                    # banco: es la mejor evidencia disponible antes de
                    # descolgar, y separa el cargo mal entendido del fraude.
                    votar(CallIntent.DISPUTA_FRAUDE, 3.0)
                else:
                    votar(CallIntent.DISPUTA_CARGO_NO_RECONOCIDO, 2.0)
        evidencia.append(f"{ev['summary']} ({fmt_fecha_hora(ev['occurred_at'])})")

    # Reintentos rechazados en cadena: un cliente que compra no reintenta dos
    # veces el mismo monto tras un rechazo; un defraudador probando una tarjeta,
    # sí.
    if rechazos_seguidos and any(
        e["kind"] == "cobro_inusual" and e["severity"] in ("alto", "critico")
        for e in señales.account_events[:3]
    ):
        votar(CallIntent.DISPUTA_FRAUDE, 1.5)

    # 4. Intentos fallidos en la app: el teléfono se usa cuando el autoservicio
    #    ya falló, así que un fallo repetido es una señal fuerte.
    fallidos = [j for j in señales.journey if not j["succeeded"] and j["channel"] == "app"]
    if fallidos:
        pantalla = fallidos[0]["screen"]
        if pantalla in _POR_PANTALLA:
            votar(_POR_PANTALLA[pantalla], 1.5 + 0.3 * min(len(fallidos), 4))
        evidencia.append(f"{len(fallidos)} intentos fallidos en la app ({pantalla})")

    # 5. Opción marcada en el IVR: el cliente ya dijo para qué llama.
    ivr = [j for j in señales.journey if j["channel"] == "ivr"]
    if ivr:
        opcion = ivr[-1]["screen"]
        for intent, peso in _POR_IVR.get(opcion, ()):
            votar(intent, peso)
        evidencia.append(f"Marcó {opcion} en el IVR")

    if duplicado is not None:
        # Evidencia exacta: la conclusión está fijada. Las señales
        # circunstanciales sólo suben la confianza dentro de un rango alto.
        apoyo = min(len(evidencia), 4)
        return IntentPrediction(
            intent=CallIntent.DISPUTA_COBRO_DUPLICADO,
            confidence=round(min(0.80 + 0.03 * apoyo, 0.92), 2),
            evidence=tuple(evidencia),
            source="pre_pop",
        )

    if not votos:
        return IntentPrediction(
            intent=CallIntent.DESCONOCIDA,
            confidence=0.0,
            evidence=("Sin señales previas: el motivo se determinará en la conversación.",),
            source="pre_pop",
        )

    ganador = max(votos, key=lambda k: votos[k])
    total = sum(votos.values())
    # La confianza combina cuán dominante es el ganador con cuánta evidencia lo
    # respalda, y se topa en 0.92: el pre-pop no puede declararse infalible
    # porque todavía no ha oído hablar al cliente.
    dominancia = votos[ganador] / total
    confianza = min(0.35 + 0.45 * dominancia + 0.06 * len(evidencia), 0.92)

    return IntentPrediction(
        intent=ganador,
        confidence=round(confianza, 2),
        evidence=tuple(evidencia),
        source="pre_pop",
    )
