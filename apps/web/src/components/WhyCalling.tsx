import { diasHabilesHasta, fmtFecha, hace } from "../lib/format";
import type { AccountEvent, Case, DigitalJourneyEvent, IntentPrediction } from "../lib/types";

const ETIQUETA_INTENCION: Record<string, string> = {
  disputa_cargo_no_reconocido: "Disputa por cargo no reconocido",
  disputa_fraude: "Posible fraude",
  disputa_cobro_duplicado: "Cobro duplicado",
  disputa_servicio_no_recibido: "Servicio no recibido",
  reclamo_comision: "Reclamo por comisión",
  reclamo_tasa_interes: "Reclamo por tasa de interés",
  seguimiento_reclamo: "Seguimiento de reclamo",
  consulta_saldo: "Consulta de saldo",
  consulta_movimiento: "Consulta de movimiento",
  tarjeta_bloqueada: "Tarjeta bloqueada",
  tarjeta_rechazada: "Tarjeta rechazada",
  actualizacion_datos: "Actualización de datos",
  clave_acceso: "Clave de acceso",
  consulta_producto: "Consulta de producto",
  solicitud_credito: "Solicitud de crédito",
  aumento_linea: "Aumento de línea",
  cancelacion_producto: "Cancelación de producto",
  desconocida: "Motivo por determinar",
};

interface Props {
  intent: IntentPrediction;
  events: AccountEvent[];
  journey: DigitalJourneyEvent[];
  cases: Case[];
}

/**
 * Zona 1: por qué llama.
 *
 * Reemplaza al perfil del cliente como elemento principal del workspace. Con
 * el 57% de las llamadas exigiendo reunir contexto y un 20-30% del tiempo del
 * ejecutivo perdido en cambiar de pantalla, lo que hace falta primero no es la
 * ficha completa: es el motivo probable de ESTA llamada, con su evidencia.
 */
export function WhyCalling({ intent, journey, cases }: Props) {
  const fallidos = journey.filter((j) => !j.succeeded);

  return (
    <section className="card">
      <header>
        <h2>Por qué llama</h2>
        <span className="confidence">
          <span className="track">
            <span className="fill" style={{ width: `${Math.round(intent.confidence * 100)}%` }} />
          </span>
          {Math.round(intent.confidence * 100)}%
        </span>
      </header>

      <div className="body">
        <div className="intent">
          <span className="label">{ETIQUETA_INTENCION[intent.intent] ?? intent.intent}</span>
        </div>

        {/*
          La evidencia no es decorativa. Una predicción sin razones visibles
          deja de mirarse a la semana, porque el ejecutivo no tiene forma de
          saber cuándo confiar en ella.
        */}
        <ul className="evidence">
          {intent.evidence.map((e) => (
            <li key={e}>{e}</li>
          ))}
        </ul>

        {cases.length > 0 && (
          <div style={{ marginTop: 14, paddingTop: 12, borderTop: "1px solid var(--line)" }}>
            {cases.map((c) => {
              const dias = diasHabilesHasta(c.due_at);
              const vencido = dias < 0;
              const urgente = !vencido && dias <= 3;
              return (
                <div key={c.case_id} className="sla">
                  <span className={`pill ${vencido ? "danger" : urgente ? "warn" : "mute"}`}>
                    {c.case_type === "reclamo" ? "Reclamo" : "Requerimiento"}
                    {vencido
                      ? ` vencido hace ${Math.abs(dias)} d hábiles`
                      : ` vence en ${dias} d hábiles`}
                  </span>
                  <span className="folio">{c.folio}</span>
                  <span style={{ color: "var(--ink-3)", fontSize: 12 }}>
                    plazo {fmtFecha(c.due_at)} · Ley 31763
                  </span>
                </div>
              );
            })}
          </div>
        )}

        {fallidos.length > 0 && (
          <details style={{ marginTop: 12 }}>
            <summary style={{ cursor: "pointer", fontSize: 12.5, color: "var(--ink-2)" }}>
              Recorrido digital antes de llamar ({journey.length} pasos, {fallidos.length} fallidos)
            </summary>
            <ul className="evidence" style={{ marginTop: 8 }}>
              {journey.map((j, i) => (
                <li key={`${j.occurred_at}-${i}`}>
                  <span style={{ color: j.succeeded ? "var(--ink-2)" : "var(--danger)" }}>
                    {j.channel === "ivr" ? "IVR" : "App"} · {j.screen} · {j.action}
                    {j.detail ? ` — ${j.detail}` : ""} ({hace(j.occurred_at)})
                  </span>
                </li>
              ))}
            </ul>
          </details>
        )}
      </div>
    </section>
  );
}
