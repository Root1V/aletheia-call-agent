import { useQuery } from "@tanstack/react-query";
import { Search, ShieldAlert } from "lucide-react";
import { useDeferredValue, useState } from "react";

import { AppShell } from "@/components/layout/AppShell";
import { Cargando, ErrorDeCarga, Vacio } from "@/components/StateMessage";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { mensajeDeError } from "@/lib/api/client";
import { endpoints, queryKeys } from "@/lib/api/endpoints";

export function CustomersPage() {
  const [texto, setTexto] = useState("");
  // El valor diferido evita una petición por pulsación sin escribir un debounce
  // a mano: React entrega el último valor cuando el tecleo se calma.
  const consulta = useDeferredValue(texto);

  const clientes = useQuery({
    queryKey: queryKeys.customers(consulta),
    queryFn: () => endpoints.customers(consulta),
  });

  return (
    <AppShell titulo="Clientes" subtitulo="Búsqueda por nombre o documento, sin distinguir tildes">
      <Card className="max-w-6xl overflow-hidden">
        <div className="border-b border-border p-4">
          <div className="relative max-w-md">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Sanchez, Quispe, ***4521…"
              className="pl-9"
              value={texto}
              onChange={(e) => setTexto(e.target.value)}
            />
          </div>
        </div>

        {clientes.isPending ? (
          <Cargando />
        ) : clientes.isError ? (
          <ErrorDeCarga
            mensaje={mensajeDeError(clientes.error)}
            onReintentar={() => clientes.refetch()}
          />
        ) : clientes.data.length === 0 ? (
          <Vacio texto={`Sin resultados para "${consulta}".`} />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-[0.7rem] uppercase tracking-wider text-muted-foreground">
                  <th className="px-4 py-2.5 font-semibold">Cliente</th>
                  <th className="px-4 py-2.5 font-semibold">Documento</th>
                  <th className="px-4 py-2.5 font-semibold">Segmento</th>
                  <th className="px-4 py-2.5 font-semibold">Ubicación</th>
                  <th className="px-4 py-2.5 text-right font-semibold">Productos</th>
                  <th className="px-4 py-2.5 text-right font-semibold">Reclamos</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {clientes.data.map((c) => (
                  <tr key={c.customer_id} className="transition-colors hover:bg-muted/50">
                    <td className="px-4 py-2.5">
                      <span className="font-medium">{c.full_name}</span>
                      {c.vulnerabilities.length > 0 && (
                        <Badge
                          variant="warning"
                          className="ml-2"
                          title="Vulnerabilidad declarada por el cliente. Sólo se usa para adaptar el trato, nunca para precios ni ofertas."
                        >
                          <ShieldAlert className="size-3" />
                          Trato adaptado
                        </Badge>
                      )}
                    </td>
                    <td className="tabular px-4 py-2.5 font-mono text-xs text-muted-foreground">
                      {c.document_masked}
                    </td>
                    <td className="px-4 py-2.5">
                      <Badge variant="muted">{c.segment}</Badge>
                    </td>
                    <td className="px-4 py-2.5 text-muted-foreground">
                      {c.district ?? c.city ?? "—"}
                    </td>
                    <td className="tabular px-4 py-2.5 text-right">{c.productos}</td>
                    <td className="tabular px-4 py-2.5 text-right">
                      {c.casos_abiertos > 0 ? (
                        <Badge variant="warning">{c.casos_abiertos}</Badge>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </AppShell>
  );
}
