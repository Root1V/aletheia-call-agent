import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Info, XCircle } from "lucide-react";

import { AppShell } from "@/components/layout/AppShell";
import { Cargando, ErrorDeCarga } from "@/components/StateMessage";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { mensajeDeError } from "@/lib/api/client";
import { endpoints, queryKeys } from "@/lib/api/endpoints";
import { fmtMonto } from "@/lib/format";
import { ETIQUETA_INTENCION } from "@/lib/intents";

export function EvaluationPage() {
  const escenarios = useQuery({
    queryKey: queryKeys.evaluation,
    queryFn: endpoints.evaluationScenarios,
  });

  return (
    <AppShell
      titulo="Conjunto de evaluación"
      subtitulo="La verdad de referencia contra la que se mide el copiloto"
    >
      <div className="max-w-5xl space-y-4">
        <Card className="border-primary/30 bg-primary-soft/40">
          <CardContent className="flex gap-3">
            <Info className="mt-0.5 size-5 shrink-0 text-primary" />
            <div className="space-y-2 text-sm">
              <p>
                Estos son los mismos escenarios que alimentan la bandeja, con lo que{" "}
                <span className="font-medium">debería</span> concluir el copiloto en cada uno. Poder
                mirar la verdad de referencia evita la discusión de «¿contra qué se midió?» en la
                reunión de resultados.
              </p>
              <p className="text-muted-foreground">
                El caso más importante es el que <span className="font-medium">no</span> debe
                terminar en reclamo: abrir uno por cada cargo mal entendido satura la operación y
                dispara los plazos de la Ley 31763 sin motivo.
              </p>
            </div>
          </CardContent>
        </Card>

        <Card className="overflow-hidden">
          <CardHeader>
            <CardTitle>Escenarios</CardTitle>
            <span className="text-xs text-muted-foreground">
              Reproducibles a partir de una semilla
            </span>
          </CardHeader>

          {escenarios.isPending ? (
            <Cargando />
          ) : escenarios.isError ? (
            <ErrorDeCarga
              mensaje={mensajeDeError(escenarios.error)}
              onReintentar={() => escenarios.refetch()}
            />
          ) : (
            <ul className="divide-y divide-border">
              {escenarios.data.map((s) => (
                <li key={s.scenario_id} className="p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">
                      {ETIQUETA_INTENCION[s.expected_intent] ?? s.expected_intent}
                    </span>
                    <Badge variant="muted">{s.customer_name}</Badge>
                    {s.expects_case ? (
                      <Badge variant={s.expected_case_type === "reclamo" ? "warning" : "default"}>
                        <CheckCircle2 className="size-3" />
                        Debe abrir {s.expected_case_type}
                      </Badge>
                    ) : (
                      <Badge variant="success">
                        <XCircle className="size-3" />
                        No debe abrir caso
                      </Badge>
                    )}
                  </div>

                  <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{s.narrative}</p>

                  {s.focus_descriptor && (
                    <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 rounded-md bg-muted/60 px-3 py-2 text-xs">
                      <span className="font-mono text-muted-foreground">{s.focus_descriptor}</span>
                      <span className="text-muted-foreground">→</span>
                      <span className="font-medium">{s.focus_merchant ?? "sin resolver"}</span>
                      {s.focus_amount && (
                        <span className="tabular font-medium">{fmtMonto(s.focus_amount)}</span>
                      )}
                      <span
                        className={
                          s.prior_purchases_90d && s.prior_purchases_90d > 0
                            ? "text-success"
                            : "text-danger"
                        }
                      >
                        {s.prior_purchases_90d && s.prior_purchases_90d > 0
                          ? `${s.prior_purchases_90d} compras previas`
                          : "sin compras previas"}
                      </span>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </AppShell>
  );
}
