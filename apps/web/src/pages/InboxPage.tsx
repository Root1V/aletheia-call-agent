import { useQuery } from "@tanstack/react-query";
import { ChevronRight, PhoneIncoming } from "lucide-react";
import { Link } from "react-router-dom";

import { AvisoDatosCaducados } from "@/components/AvisoDatosCaducados";
import { AppShell } from "@/components/layout/AppShell";
import { Cargando, ErrorDeCarga, Vacio } from "@/components/StateMessage";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { mensajeDeError } from "@/lib/api/client";
import { endpoints, queryKeys } from "@/lib/api/endpoints";
import { ETIQUETA_INTENCION } from "@/lib/intents";

export function InboxPage() {
  const bandeja = useQuery({ queryKey: queryKeys.inbound, queryFn: endpoints.inbound });
  const stats = useQuery({ queryKey: queryKeys.overview, queryFn: endpoints.overview });

  return (
    <AppShell
      titulo="Bandeja de llamadas"
      subtitulo="Escenarios guionados y reproducibles: los mismos datos alimentan la demo y la evaluación"
    >
      <div className="mb-4 max-w-4xl">
        <AvisoDatosCaducados horas={stats.data?.datos_sembrados_hace_horas ?? null} />
      </div>

      {bandeja.isPending ? (
        <Cargando />
      ) : bandeja.isError ? (
        <Card>
          <ErrorDeCarga
            mensaje={mensajeDeError(bandeja.error)}
            onReintentar={() => bandeja.refetch()}
          />
        </Card>
      ) : bandeja.data.length === 0 ? (
        <Card>
          <Vacio texto="No hay escenarios cargados. Ejecutar `make seed`." />
        </Card>
      ) : (
        <div className="grid max-w-4xl gap-3">
          {bandeja.data.map((c) => (
            <Link
              key={c.call_id}
              to={`/llamadas/${c.call_id}`}
              className="group rounded-lg border border-border bg-card p-4 shadow-xs transition-all hover:-translate-y-px hover:border-primary/50 hover:shadow-sm"
            >
              <div className="flex items-start gap-4">
                <span className="grid size-11 shrink-0 place-items-center rounded-lg bg-primary-soft text-primary">
                  <PhoneIncoming className="size-5" />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold">{c.customer_name}</span>
                    <Badge variant="muted">{c.segment}</Badge>
                    <Badge>{ETIQUETA_INTENCION[c.scenario_id] ?? c.scenario_id}</Badge>
                  </div>
                  <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
                    {c.narrative}
                  </p>
                </div>
                <ChevronRight className="mt-1 size-5 shrink-0 text-muted-foreground/50 transition-transform group-hover:translate-x-0.5 group-hover:text-primary" />
              </div>
            </Link>
          ))}
        </div>
      )}
    </AppShell>
  );
}
