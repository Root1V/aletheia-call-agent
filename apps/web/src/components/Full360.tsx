import { fmtMonto } from "../lib/format";
import type { Customer } from "../lib/types";

/**
 * Zona 6: el 360 completo, colapsado por defecto.
 *
 * Está plegado por diseño y no por falta de espacio. Un panel que lo muestra
 * todo, siempre, es el paradigma CRM antiguo: lo que el ejecutivo necesita
 * durante la llamada es el contexto de ESTA conversación, con el resto a un
 * clic. La ficha completa sigue estando; simplemente deja de competir por la
 * atención mientras el cliente habla.
 */
export function Full360({ customer }: { customer: Customer }) {
  return (
    <section className="card">
      <details className="full360">
        <summary>
          Ver 360 completo — {customer.holdings.length} productos
          {customer.nps !== null ? ` · NPS ${customer.nps}` : ""}
          {customer.city ? ` · ${customer.district ?? customer.city}` : ""}
        </summary>

        <ul className="holdings">
          {customer.holdings.map((h) => {
            const saldo = h.balance !== null ? Number(h.balance) : null;
            return (
              <li key={h.holding_id} className="holding">
                <span style={{ minWidth: 0 }}>
                  <div style={{ fontWeight: 560 }}>{h.product_name}</div>
                  {h.masked_number && <span className="num">{h.masked_number}</span>}
                </span>
                <span style={{ textAlign: "right" }}>
                  {saldo !== null && (
                    <div className={`bal ${saldo < 0 ? "neg" : ""}`}>
                      {fmtMonto(h.balance!, h.currency)}
                    </div>
                  )}
                  {h.credit_limit && (
                    <div style={{ fontSize: 11.5, color: "var(--ink-3)" }}>
                      línea {fmtMonto(h.credit_limit, h.currency)}
                    </div>
                  )}
                </span>
              </li>
            );
          })}
        </ul>
      </details>
    </section>
  );
}
