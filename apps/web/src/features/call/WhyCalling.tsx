import { ChevronRight } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { diasHabilesHasta, fmtFecha, hace } from "@/lib/format";
import { ETIQUETA_INTENCION } from "@/lib/intents";
import type { Case, DigitalJourneyEvent, IntentPrediction } from "@/lib/types";

/**
 * Zona 1: por qué llama.
 *
 * Reemplaza al perfil del cliente como elemento principal. Con el 57% de las
 * llamadas exigiendo reunir contexto y un 20-30% del tiempo perdido en cambiar
 * de pantalla, lo primero que hace falta no es la ficha completa: es el motivo
 * probable de ESTA llamada, con su evidencia.
 */
export function WhyCalling({
  intent,
  journey,
  cases,
}: {
  intent: IntentPrediction;
  journey: DigitalJourneyEvent[];
  cases: Case[];
}) {
  const fallidos = journey.filter((j) => !j.succeeded);
  const pct = Math.round(intent.confidence * 100);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Por qué llama</CardTitle>
        <span className="flex items-center gap-2 text-xs text-muted-foreground">
          <span className="h-1 w-12 overflow-hidden rounded-full bg-border">
            <span className="block h-full bg-primary" style={{ width: `${pct}%` }} />
          </span>
          <span className="tabular">{pct}%</span>
        </span>
      </CardHeader>

      <CardContent>
        <p className="text-base font-semibold leading-snug">
          {ETIQUETA_INTENCION[intent.intent] ?? intent.intent}
        </p>

        {/*
          La evidencia no es decorativa: una predicción sin razones visibles deja
          de mirarse a la semana, porque el ejecutivo no tiene forma de saber
          cuándo confiar en ella.
        */}
        <ul className="mt-3 space-y-1.5">
          {intent.evidence.map((e) => (
            <li key={e} className="flex gap-2 text-sm leading-relaxed text-muted-foreground">
              <span aria-hidden className="text-muted-foreground/50">
                ·
              </span>
              <span>{e}</span>
            </li>
          ))}
        </ul>

        {cases.length > 0 && (
          <div className="mt-4 space-y-2 border-t border-border pt-3">
            {cases.map((c) => {
              const dias = diasHabilesHasta(c.due_at);
              const vencido = dias < 0;
              const urgente = !vencido && dias <= 3;
              return (
                <div key={c.case_id} className="flex flex-wrap items-baseline gap-2">
                  <Badge variant={vencido ? "danger" : urgente ? "warning" : "muted"}>
                    {c.case_type === "reclamo" ? "Reclamo" : "Requerimiento"}
                    {vencido
                      ? ` vencido hace ${Math.abs(dias)} d hábiles`
                      : ` vence en ${dias} d hábiles`}
                  </Badge>
                  <span className="font-mono text-xs text-muted-foreground">{c.folio}</span>
                  <span className="text-xs text-muted-foreground">
                    plazo {fmtFecha(c.due_at)} · Ley 31763
                  </span>
                </div>
              );
            })}
          </div>
        )}

        {journey.length > 0 && (
          <details className="group mt-3">
            <summary className="flex cursor-pointer list-none items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground">
              <ChevronRight className="size-3.5 transition-transform group-open:rotate-90" />
              Recorrido digital antes de llamar ({journey.length} pasos, {fallidos.length} fallidos)
            </summary>
            <ul className="mt-2 space-y-1.5 pl-5">
              {journey.map((j, i) => (
                <li
                  key={`${j.occurred_at}-${i}`}
                  className={`text-xs leading-relaxed ${j.succeeded ? "text-muted-foreground" : "text-danger"}`}
                >
                  {j.channel === "ivr" ? "IVR" : "App"} · {j.screen} · {j.action}
                  {j.detail ? ` — ${j.detail}` : ""} ({hace(j.occurred_at)})
                </li>
              ))}
            </ul>
          </details>
        )}
      </CardContent>
    </Card>
  );
}
