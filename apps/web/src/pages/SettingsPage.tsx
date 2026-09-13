import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, XCircle } from "lucide-react";

import { AppShell } from "@/components/layout/AppShell";
import { Cargando } from "@/components/StateMessage";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/features/auth/auth-context";
import { endpoints, queryKeys } from "@/lib/api/endpoints";

function Fila({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 py-2.5">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-medium">{children}</span>
    </div>
  );
}

export function SettingsPage() {
  const { agent } = useAuth();
  const health = useQuery({ queryKey: queryKeys.health, queryFn: endpoints.health });

  return (
    <AppShell titulo="Ajustes" subtitulo="Sesión y estado del sistema">
      <div className="grid max-w-4xl gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Tu sesión</CardTitle>
          </CardHeader>
          <CardContent className="divide-y divide-border py-0">
            <Fila label="Nombre">{agent?.name}</Fila>
            <Fila label="Usuario">
              <span className="font-mono text-xs">@{agent?.username}</span>
            </Fila>
            <Fila label="Roles">
              <span className="flex flex-wrap gap-1">
                {agent?.roles.map((r) => (
                  <Badge key={r} variant="muted">
                    {r}
                  </Badge>
                ))}
              </span>
            </Fila>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Estado del sistema</CardTitle>
          </CardHeader>
          {health.isPending ? (
            <Cargando texto="Consultando…" />
          ) : health.isError ? (
            <CardContent>
              <Badge variant="danger">
                <XCircle className="size-3" />
                API no disponible
              </Badge>
            </CardContent>
          ) : (
            <CardContent className="divide-y divide-border py-0">
              <Fila label="Base de datos">
                {health.data.postgres.ok ? (
                  <Badge variant="success">
                    <CheckCircle2 className="size-3" />
                    Conectada
                  </Badge>
                ) : (
                  <Badge variant="danger">
                    <XCircle className="size-3" />
                    Sin conexión
                  </Badge>
                )}
              </Fila>
              <Fila label="Autenticación">
                <Badge variant="muted">
                  {health.data.auth_mode === "local" ? "JWT propio" : "SSO corporativo"}
                </Badge>
              </Fila>
              <Fila label="Entorno">
                <Badge variant={health.data.entorno === "dev" ? "muted" : "warning"}>
                  {health.data.entorno}
                </Badge>
              </Fila>
              {/*
                El presupuesto de latencia se muestra aquí y sale del mismo
                /health que consultan Grafana y las evaluaciones. Tenerlo en un
                solo sitio evita que tres lugares afirmen objetivos distintos.
              */}
              <Fila label="Transcripción visible">
                <span className="tabular">
                  &lt; {health.data.presupuesto_latencia_ms.transcripcion_visible} ms
                </span>
              </Fila>
              <Fila label="Sugerencia visible">
                <span className="tabular">
                  &lt; {health.data.presupuesto_latencia_ms.sugerencia_visible} ms
                </span>
              </Fila>
            </CardContent>
          )}
        </Card>
      </div>
    </AppShell>
  );
}
