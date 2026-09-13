import { Fragment } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { fmtFechaHora, fmtMonto } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Transaction } from "@/lib/types";

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
 * vistazo.
 */
function iniciales(nombre: string): string {
  const palabras = nombre.split(/\s+/).filter(Boolean);
  if (palabras.length >= 2) return (palabras[0]![0]! + palabras[1]![0]!).toUpperCase();
  return (palabras[0] ?? "?").slice(0, 2).toUpperCase();
}

/**
 * Zona 2: la evidencia que resuelve la disputa.
 *
 * El panel de mayor palanca del flujo de reclamos. El 61% de las disputas se
 * abren porque el cliente no reconoce un cargo —no por fraude— y ésas generan
 * más insatisfacción que las de fraude real. Traducir "DLO*RAPPI PE 5511234567"
 * a "Rappi, pedido del 3 de setiembre desde su iPhone, con 5 compras previas"
 * cierra buena parte de esas llamadas sin abrir un caso.
 *
 * Por eso se conserva y se muestra el descriptor crudo: es el texto que el
 * cliente tiene delante en su estado de cuenta.
 */
export function TransactionEvidence({
  transactions,
  focusId,
  supportingIds,
  attemptIds,
}: {
  transactions: Transaction[];
  focusId: string | null;
  supportingIds: string[];
  attemptIds: string[];
}) {
  const soporte = new Set(supportingIds);
  const intentos = new Set(attemptIds);
  const foco = transactions.find((t) => t.transaction_id === focusId) ?? null;
  const comercio = foco?.merchant?.display_name ?? "el mismo comercio";

  // El cargo en disputa primero, luego los intentos relacionados, luego las
  // compras previas, y el resto al final. El orden cronológico enterraría la
  // transacción que motiva la llamada entre movimientos irrelevantes.
  const rango = (t: Transaction) =>
    t.transaction_id === focusId
      ? 0
      : intentos.has(t.transaction_id)
        ? 1
        : soporte.has(t.transaction_id)
          ? 2
          : 3;

  const ordenadas = [...transactions].sort((a, b) => {
    const d = rango(a) - rango(b);
    return d !== 0 ? d : b.occurred_at.localeCompare(a.occurred_at);
  });

  return (
    <Card className="overflow-hidden">
      <CardHeader>
        <CardTitle>Movimientos</CardTitle>
        {foco?.merchant && soporte.size > 0 && (
          <Badge variant="success">
            {soporte.size} compras previas en {foco.merchant.display_name}
          </Badge>
        )}
        {foco?.merchant && soporte.size === 0 && intentos.size > 0 && (
          <Badge variant="danger">
            {intentos.size} intentos más en {foco.merchant.display_name}
          </Badge>
        )}
      </CardHeader>

      {ordenadas.length === 0 ? (
        <p className="px-4 py-8 text-center text-sm text-muted-foreground">
          Sin movimientos relevantes para este motivo.
        </p>
      ) : (
        <ul>
          {ordenadas.map((t, i) => {
            const esFoco = t.transaction_id === focusId;
            const esSoporte = soporte.has(t.transaction_id);
            const esIntento = intentos.has(t.transaction_id);
            const m = t.merchant;
            const anterior = ordenadas[i - 1];
            const abre = (r: number) => rango(t) === r && (i === 0 || rango(anterior!) !== r);

            return (
              <Fragment key={t.transaction_id}>
                {/* Encabezados de grupo. Sin ellos, siete movimientos seguidos
                    del mismo comercio parecen un error de datos en vez de la
                    prueba deliberada que son. */}
                {abre(1) && (
                  <li className="border-y border-border bg-danger-soft px-4 py-2 text-[0.65rem] font-semibold uppercase tracking-wider text-danger">
                    Otros intentos en {comercio} después del cargo — evidencia de fraude, no
                    historial del cliente
                  </li>
                )}
                {abre(2) && (
                  <li className="border-y border-border bg-muted px-4 py-2 text-[0.65rem] font-semibold uppercase tracking-wider text-muted-foreground">
                    Compras previas en {comercio} — respaldo de la explicación
                  </li>
                )}
                {abre(3) && (
                  <li className="border-y border-border bg-muted px-4 py-2 text-[0.65rem] font-semibold uppercase tracking-wider text-muted-foreground">
                    Otros movimientos recientes
                  </li>
                )}

                <li
                  className={cn(
                    "flex gap-3 border-b border-border px-4 py-3 last:border-b-0",
                    esFoco && "border-l-[3px] border-l-primary bg-primary-soft pl-[13px]",
                    esIntento && "bg-danger-soft/50",
                    esSoporte && "bg-muted/40",
                  )}
                >
                  <span
                    className="grid size-8 shrink-0 place-items-center rounded-lg border border-border bg-card text-[0.7rem] font-semibold text-muted-foreground"
                    aria-hidden
                  >
                    {m ? iniciales(m.display_name) : "?"}
                  </span>

                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium">
                        {m ? m.display_name : "Comercio no identificado"}
                      </span>
                      {esFoco && <Badge>en consulta</Badge>}
                    </div>

                    <p className="mt-0.5 text-xs text-muted-foreground">
                      {fmtFechaHora(t.occurred_at)}
                      {m?.category ? ` · ${m.category}` : ""}
                      {m?.district ? ` · ${m.district}` : ""}
                      {` · ${ETIQUETA_CANAL[t.channel] ?? t.channel}`}
                      {/* El dispositivo sólo significa algo en canales
                          digitales: en una compra presencial no hay dispositivo
                          del cliente, y mostrar "no reconocido" ahí inventaría
                          una alarma donde no la hay. */}
                      {t.device_label
                        ? ` · ${t.device_label}`
                        : t.channel === "ecommerce" || t.channel === "app"
                          ? " · dispositivo no reconocido"
                          : ""}
                    </p>

                    <p className="mt-1 break-all font-mono text-[0.7rem] text-muted-foreground/80">
                      {t.raw_descriptor}
                    </p>

                    {t.decline_reason && (
                      <p className="mt-1 text-xs text-danger">{t.decline_reason}</p>
                    )}

                    {esFoco && m && t.prior_purchases_90d > 0 && (
                      <p className="mt-2 rounded-md bg-success-soft px-2.5 py-1.5 text-xs font-medium text-success">
                        El cliente compró {t.prior_purchases_90d} veces en {m.display_name} en los
                        últimos 90 días
                        {t.device_label ? `, desde su ${t.device_label}` : ""}.
                      </p>
                    )}
                    {esFoco && t.prior_purchases_90d === 0 && (
                      <p className="mt-2 rounded-md bg-danger-soft px-2.5 py-1.5 text-xs font-medium text-danger">
                        Sin compras previas en este comercio
                        {!t.device_label && ", y sin dispositivo reconocido"}.
                      </p>
                    )}
                  </div>

                  <div className="shrink-0 text-right">
                    <p className="tabular font-semibold">{fmtMonto(t.amount, t.currency)}</p>
                    <p
                      className={cn(
                        "text-[0.7rem]",
                        t.status === "rechazada"
                          ? "text-danger"
                          : t.status === "pendiente"
                            ? "text-warning"
                            : "text-muted-foreground",
                      )}
                    >
                      {t.status}
                    </p>
                  </div>
                </li>
              </Fragment>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
