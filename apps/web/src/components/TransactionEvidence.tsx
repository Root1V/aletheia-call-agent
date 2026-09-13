import { Fragment } from "react";

import { fmtFechaHora, fmtMonto } from "../lib/format";
import type { Transaction } from "../lib/types";

interface Props {
  transactions: Transaction[];
  focusId: string | null;
  supportingIds: string[];
  attemptIds: string[];
}

const ETIQUETA_CANAL: Record<string, string> = {
  app: "app",
  web: "web",
  pos: "presencial",
  atm: "cajero",
  ecommerce: "internet",
  ivr: "IVR",
  agencia: "agencia",
  call_center: "call center",
};

/**
 * Marcador de dos letras mientras no haya logos reales.
 *
 * Con una inicial por palabra, "inDrive" o "Rappi" quedaban en una sola letra
 * dentro de un cuadro: ilegible y sin valor para distinguir comercios de un
 * vistazo. Dos caracteres bastan para diferenciar, y el logo real los sustituye
 * en cuanto el catálogo los traiga.
 */
function iniciales(nombre: string): string {
  const palabras = nombre.split(/\s+/).filter(Boolean);
  if (palabras.length >= 2) {
    return (palabras[0]![0]! + palabras[1]![0]!).toUpperCase();
  }
  return (palabras[0] ?? "?").slice(0, 2).toUpperCase();
}

/**
 * Zona 2: la evidencia que resuelve la disputa.
 *
 * Este panel es la palanca más alta del flujo de reclamos. El 61% de las
 * disputas se abren porque el cliente no reconoce un cargo —no por fraude— y
 * esas generan más insatisfacción que las de fraude real. Traducir
 * "DLO*RAPPI PE 5511234567" a "Rappi, pedido del 3 de setiembre desde su
 * iPhone, con 5 compras previas" cierra buena parte de esas llamadas sin abrir
 * un caso.
 *
 * Por eso se conserva y se muestra el descriptor crudo: es el texto que el
 * cliente tiene delante en su estado de cuenta, y el ejecutivo necesita tender
 * el puente entre ese texto y el comercio real.
 */
export function TransactionEvidence({ transactions, focusId, supportingIds, attemptIds }: Props) {
  const soporte = new Set(supportingIds);
  const intentos = new Set(attemptIds);
  const foco = transactions.find((t) => t.transaction_id === focusId) ?? null;

  // El cargo en disputa primero, luego los intentos relacionados, luego las
  // compras previas, y el resto al final. El orden cronológico enterraría la
  // transacción que motiva la llamada entre movimientos irrelevantes.
  const rango = (t: Transaction) =>
    t.transaction_id === focusId ? 0 : intentos.has(t.transaction_id) ? 1
      : soporte.has(t.transaction_id) ? 2 : 3;

  const ordenadas = [...transactions].sort((a, b) => {
    const d = rango(a) - rango(b);
    return d !== 0 ? d : b.occurred_at.localeCompare(a.occurred_at);
  });

  return (
    <section className="card">
      <header>
        <h2>Movimientos</h2>
        {foco?.merchant && soporte.size > 0 && (
          <span className="pill ok">
            {soporte.size} compras previas en {foco.merchant.display_name}
          </span>
        )}
        {foco?.merchant && soporte.size === 0 && intentos.size > 0 && (
          <span className="pill danger">
            {intentos.size} intentos más en {foco.merchant.display_name}
          </span>
        )}
      </header>

      <div className="body tight">
        {ordenadas.length === 0 ? (
          <p className="empty">Sin movimientos relevantes para este motivo.</p>
        ) : (
          <ul className="txlist">
            {ordenadas.map((t, i) => {
              const esFoco = t.transaction_id === focusId;
              const esSoporte = soporte.has(t.transaction_id);
              const esIntento = intentos.has(t.transaction_id);
              const m = t.merchant;

              // Encabezados de grupo. Sin ellos, siete movimientos seguidos del
              // mismo comercio parecen un error de datos en vez de la prueba
              // deliberada que son.
              const anterior = ordenadas[i - 1];
              const abre = (r: number) => rango(t) === r && (i === 0 || rango(anterior!) !== r);
              const comercio = foco?.merchant?.display_name ?? "el mismo comercio";

              return (
                <Fragment key={t.transaction_id}>
                  {abre(1) && (
                    <li className="group danger">
                      Otros intentos en {comercio} después del cargo — evidencia de fraude, no
                      historial del cliente
                    </li>
                  )}
                  {abre(2) && (
                    <li className="group">
                      Compras previas en {comercio} — respaldo de la explicación
                    </li>
                  )}
                  {abre(3) && <li className="group">Otros movimientos recientes</li>}
                <li
                  className={`tx ${esFoco ? "focus" : esIntento ? "attempt" : esSoporte ? "support" : ""}`}
                >
                  <span className="logo" aria-hidden>
                    {m ? iniciales(m.display_name) : "?"}
                  </span>

                  <div style={{ minWidth: 0 }}>
                    <div className="merchant">
                      {m ? m.display_name : "Comercio no identificado"}
                      {esFoco && (
                        <span className="pill info" style={{ marginLeft: 8 }}>
                          en consulta
                        </span>
                      )}
                    </div>

                    <div className="sub">
                      {fmtFechaHora(t.occurred_at)}
                      {m?.category ? ` · ${m.category}` : ""}
                      {m?.district ? ` · ${m.district}` : ""}
                      {` · ${ETIQUETA_CANAL[t.channel] ?? t.channel}`}
                      {/*
                        El dispositivo sólo significa algo en canales digitales.
                        En una compra presencial no hay dispositivo del cliente,
                        y mostrar "desconocido" ahí inventaría una señal de
                        alarma donde no la hay.
                      */}
                      {t.device_label
                        ? ` · ${t.device_label}`
                        : t.channel === "ecommerce" || t.channel === "app"
                          ? " · dispositivo no reconocido"
                          : ""}
                    </div>

                    <div className="raw">{t.raw_descriptor}</div>

                    {t.decline_reason && (
                      <div className="sub" style={{ color: "var(--danger)" }}>
                        {t.decline_reason}
                      </div>
                    )}

                    {esFoco && t.prior_purchases_90d > 0 && m && (
                      <div className="proof">
                        El cliente compró {t.prior_purchases_90d} veces en {m.display_name} en los
                        últimos 90 días
                        {t.device_label ? `, desde su ${t.device_label}` : ""}.
                      </div>
                    )}
                    {esFoco && t.prior_purchases_90d === 0 && (
                      <div className="proof" style={{ background: "var(--danger-bg)", color: "var(--danger)" }}>
                        Sin compras previas en este comercio
                        {!t.device_label && ", y sin dispositivo reconocido"}.
                      </div>
                    )}
                  </div>

                  <div className="amount">
                    {fmtMonto(t.amount, t.currency)}
                    <span className={`state ${t.status}`}>{t.status}</span>
                  </div>
                </li>
                </Fragment>
              );
            })}
          </ul>
        )}
      </div>
    </section>
  );
}
