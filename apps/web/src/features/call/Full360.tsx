import { ChevronRight } from "lucide-react";

import { Card } from "@/components/ui/card";
import { fmtMonto } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Customer } from "@/lib/types";

/**
 * Zona 6: el 360 completo, colapsado por defecto.
 *
 * Está plegado por diseño y no por falta de espacio. Un panel que lo muestra
 * todo, siempre, es el paradigma CRM antiguo: durante la llamada hace falta el
 * contexto de ESTA conversación, con el resto a un clic. La ficha completa
 * sigue estando; deja de competir por la atención mientras el cliente habla.
 */
export function Full360({ customer }: { customer: Customer }) {
  return (
    <Card className="overflow-hidden">
      <details className="group">
        <summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-3 text-sm text-muted-foreground transition-colors hover:text-foreground">
          <ChevronRight className="size-4 transition-transform group-open:rotate-90" />
          Ver 360 completo — {customer.holdings.length} productos
          {customer.nps !== null ? ` · NPS ${customer.nps}` : ""}
          {customer.city ? ` · ${customer.district ?? customer.city}` : ""}
        </summary>

        <ul className="space-y-2 px-4 pb-4">
          {customer.holdings.map((h) => {
            const saldo = h.balance !== null ? Number(h.balance) : null;
            return (
              <li
                key={h.holding_id}
                className="flex items-start justify-between gap-3 rounded-md border border-border bg-muted/40 px-3 py-2"
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{h.product_name}</p>
                  {h.masked_number && (
                    <p className="font-mono text-[0.7rem] text-muted-foreground">
                      {h.masked_number}
                    </p>
                  )}
                </div>
                <div className="shrink-0 text-right">
                  {saldo !== null && (
                    <p className={cn("tabular text-sm font-semibold", saldo < 0 && "text-danger")}>
                      {fmtMonto(h.balance!, h.currency)}
                    </p>
                  )}
                  {h.credit_limit && (
                    <p className="text-[0.7rem] text-muted-foreground">
                      línea {fmtMonto(h.credit_limit, h.currency)}
                    </p>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      </details>
    </Card>
  );
}
