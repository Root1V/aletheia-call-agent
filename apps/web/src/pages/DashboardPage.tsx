import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  Clock3,
  CreditCard,
  FileWarning,
  PhoneIncoming,
  Store,
  Users,
} from "lucide-react";
import { Link } from "react-router-dom";

import { AppShell } from "@/components/layout/AppShell";
import { StatCard } from "@/components/StatCard";
import { Cargando, ErrorDeCarga, Vacio } from "@/components/StateMessage";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button-variants";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/features/auth/auth-context";
import { mensajeDeError } from "@/lib/api/client";
import { endpoints, queryKeys } from "@/lib/api/endpoints";
import { ETIQUETA_INTENCION } from "@/lib/intents";

const nf = new Intl.NumberFormat("es-PE");

export function DashboardPage() {
  const { agent } = useAuth();
  const stats = useQuery({ queryKey: queryKeys.overview, queryFn: endpoints.overview });
  const bandeja = useQuery({ queryKey: queryKeys.inbound, queryFn: endpoints.inbound });

  const nombreCorto = agent?.name.split(" ")[0] ?? "";

  return (
    <AppShell
      titulo={`Hola, ${nombreCorto}`}
      subtitulo="Esto es lo que hay en la operación ahora mismo"
      acciones={
        // Link y no un onClick con window.location: una navegación completa
        // recarga el bundle y vacía la caché de react-query, así que el panel
        // vuelve a pedir todo lo que ya tenía.
        <Link to="/bandeja" className={buttonVariants()}>
          <PhoneIncoming />
          Ver bandeja
        </Link>
      }
    >
      <div className="space-y-5">
        {stats.isPending ? (
          <Cargando texto="Cargando indicadores…" />
        ) : stats.isError ? (
          <Card>
            <ErrorDeCarga
              mensaje={mensajeDeError(stats.error)}
              onReintentar={() => stats.refetch()}
            />
          </Card>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard
              icono={PhoneIncoming}
              valor={stats.data.llamadas_en_bandeja}
              etiqueta="Llamadas en bandeja"
              nota="Escenarios guionados"
            />
            <StatCard
              icono={Users}
              valor={nf.format(stats.data.clientes)}
              etiqueta="Clientes"
              nota={`${nf.format(stats.data.transacciones)} movimientos`}
            />
            <StatCard
              icono={FileWarning}
              valor={stats.data.casos_abiertos}
              etiqueta="Reclamos abiertos"
              nota={
                stats.data.casos_por_vencer > 0
                  ? `${stats.data.casos_por_vencer} vencen esta semana`
                  : "Ninguno vence esta semana"
              }
              tono={stats.data.casos_por_vencer > 0 ? "warning" : "default"}
            />
            <StatCard
              icono={Store}
              valor={stats.data.comercios}
              etiqueta="Comercios en catálogo"
              nota="Para resolver descriptores"
            />
          </div>
        )}

        <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
          <Card>
            <CardHeader>
              <CardTitle>Llamadas en espera</CardTitle>
              <Link
                to="/bandeja"
                className="flex items-center gap-1 text-xs font-medium text-primary hover:underline"
              >
                Ver todas <ArrowRight className="size-3" />
              </Link>
            </CardHeader>
            {bandeja.isPending ? (
              <Cargando />
            ) : bandeja.isError ? (
              <ErrorDeCarga
                mensaje={mensajeDeError(bandeja.error)}
                onReintentar={() => bandeja.refetch()}
              />
            ) : bandeja.data.length === 0 ? (
              <Vacio texto="No hay llamadas en espera." />
            ) : (
              <ul className="divide-y divide-border">
                {bandeja.data.slice(0, 4).map((c) => (
                  <li key={c.call_id}>
                    <Link
                      to={`/llamadas/${c.call_id}`}
                      className="flex items-start gap-3 px-4 py-3 transition-colors hover:bg-muted/60"
                    >
                      <span className="mt-0.5 grid size-9 shrink-0 place-items-center rounded-lg bg-primary-soft text-primary">
                        <PhoneIncoming className="size-4" />
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-medium">{c.customer_name}</span>
                          <Badge variant="muted">{c.segment}</Badge>
                          <Badge>{ETIQUETA_INTENCION[c.scenario_id] ?? c.scenario_id}</Badge>
                        </div>
                        <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">
                          {c.narrative}
                        </p>
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Cómo leer el panel</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-sm">
              <div className="flex gap-3">
                <span className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg bg-primary-soft text-primary">
                  <CreditCard className="size-4" />
                </span>
                <p className="text-muted-foreground">
                  El <span className="font-medium text-foreground">cargo en consulta</span> viene
                  resaltado, con el comercio real detrás del descriptor y las compras previas que
                  permiten explicarlo.
                </p>
              </div>
              <div className="flex gap-3">
                <span className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg bg-warning-soft text-warning">
                  <Clock3 className="size-4" />
                </span>
                <p className="text-muted-foreground">
                  Los reclamos abiertos muestran los{" "}
                  <span className="font-medium text-foreground">días hábiles restantes</span> del
                  plazo de la Ley 31763, no la fecha suelta.
                </p>
              </div>
              <div className="flex gap-3">
                <span className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg bg-success-soft text-success">
                  <FileWarning className="size-4" />
                </span>
                <p className="text-muted-foreground">
                  Compras <span className="font-medium text-foreground">anteriores</span> e intentos{" "}
                  <span className="font-medium text-foreground">posteriores</span> se muestran por
                  separado: significan cosas opuestas.
                </p>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </AppShell>
  );
}
