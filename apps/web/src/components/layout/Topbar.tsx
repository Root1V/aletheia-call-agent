import { LogOut, Menu, Monitor, Moon, Search, Sun } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/features/auth/auth-context";
import { useTheme, type Tema } from "@/features/theme/useTheme";
import { cn } from "@/lib/utils";

const TEMAS: { valor: Tema; icono: React.ComponentType<{ className?: string }>; label: string }[] = [
  { valor: "light", icono: Sun, label: "Claro" },
  { valor: "dark", icono: Moon, label: "Oscuro" },
  { valor: "system", icono: Monitor, label: "Sistema" },
];

export function Topbar({
  titulo,
  subtitulo,
  acciones,
  onOpenMenu,
}: {
  titulo: string;
  subtitulo?: string;
  acciones?: React.ReactNode;
  onOpenMenu?: () => void;
}) {
  const { agent, logout } = useAuth();
  const { tema, setTema } = useTheme();
  const [menuAbierto, setMenuAbierto] = useState(false);

  const iniciales = (agent?.name ?? "?")
    .split(/\s+/)
    .slice(0, 2)
    .map((p) => p[0])
    .join("")
    .toUpperCase();

  return (
    <header className="sticky top-0 z-20 border-b border-border bg-background/85 backdrop-blur">
      <div className="flex flex-wrap items-center gap-3 px-4 py-3 sm:px-6">
        <Button variant="ghost" size="icon" className="lg:hidden" onClick={onOpenMenu}>
          <Menu />
          <span className="sr-only">Abrir menú</span>
        </Button>

        <div className="min-w-0 flex-1">
          <h1 className="truncate text-xl font-semibold tracking-tight">{titulo}</h1>
          {subtitulo && (
            <p className="truncate text-sm text-muted-foreground">{subtitulo}</p>
          )}
        </div>

        <div className="relative hidden max-w-sm flex-1 md:block">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Buscar cliente por nombre o documento…"
            className="h-9 pl-9"
            readOnly
            title="La búsqueda global llega con la base de conocimiento (Fase 4). Por ahora, buscar desde Clientes."
          />
        </div>

        {acciones}

        <div className="flex items-center rounded-md border border-border p-0.5">
          {TEMAS.map((t) => (
            <button
              key={t.valor}
              onClick={() => setTema(t.valor)}
              aria-label={`Tema ${t.label.toLowerCase()}`}
              aria-pressed={tema === t.valor}
              className={cn(
                "grid size-7 place-items-center rounded transition-colors",
                tema === t.valor
                  ? "bg-muted text-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              <t.icono className="size-3.5" />
            </button>
          ))}
        </div>

        <div className="relative">
          <button
            onClick={() => setMenuAbierto((v) => !v)}
            className="flex items-center gap-2 rounded-full p-0.5 pr-2 transition-colors hover:bg-muted"
          >
            <span className="grid size-8 place-items-center rounded-full bg-gradient-to-br from-primary to-violet-500 text-xs font-semibold text-white">
              {iniciales}
            </span>
            <span className="hidden text-sm font-medium sm:inline">{agent?.name}</span>
          </button>

          {menuAbierto && (
            <>
              {/* Capa de cierre. Sin ella el menú sólo se cierra volviendo a
                  pulsar el avatar, que no es lo que nadie espera. */}
              <div
                className="fixed inset-0 z-30"
                onClick={() => setMenuAbierto(false)}
                aria-hidden
              />
              <div className="absolute right-0 z-40 mt-2 w-56 overflow-hidden rounded-lg border border-border bg-popover shadow-lg">
                <div className="border-b border-border px-3 py-2.5">
                  <p className="truncate text-sm font-medium">{agent?.name}</p>
                  <p className="truncate text-xs text-muted-foreground">@{agent?.username}</p>
                  <p className="mt-1.5 text-[0.7rem] text-muted-foreground">
                    {agent?.roles.join(" · ")}
                  </p>
                </div>
                <button
                  onClick={logout}
                  className="flex w-full items-center gap-2 px-3 py-2.5 text-sm text-danger transition-colors hover:bg-muted"
                >
                  <LogOut className="size-4" />
                  Cerrar sesión
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
