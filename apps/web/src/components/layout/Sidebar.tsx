import {
  BarChart3,
  Home,
  PhoneIncoming,
  Settings,
  Users,
} from "lucide-react";
import { NavLink } from "react-router-dom";

import { BrandMark } from "@/components/BrandMark";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface Item {
  to: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  /** Fase del plan en la que se construye. Presente = todavía no existe. */
  fase?: string;
}

interface Seccion {
  titulo?: string;
  items: Item[];
}

/*
 * El menú lista sólo lo que existe, y lo pendiente va explícitamente marcado
 * con su fase y deshabilitado.
 *
 * Un menú lleno de enlaces que no llevan a ninguna parte se ve más completo en
 * una captura, pero en cuanto alguien hace clic en la reunión queda claro que
 * la mitad del producto no está. Es más sólido decir qué falta que fingir que
 * está.
 */
const SECCIONES: Seccion[] = [
  {
    items: [
      { to: "/", label: "Inicio", icon: Home },
      { to: "/bandeja", label: "Bandeja de llamadas", icon: PhoneIncoming },
      { to: "/clientes", label: "Clientes", icon: Users },
    ],
  },
  // Aquí hubo dos entradas, "Conocimiento" y "Sugerencias", marcadas como
  // Fase 4. Se quitan porque engañaban por partida doble: la Fase 4 ya está
  // construida —el copiloto y la base de conocimiento funcionan dentro de la
  // llamada— y sus rutas nunca existieron, así que pulsarlas devolvía a inicio
  // sin decir por qué. Una zona no construida se marca donde se echa en falta,
  // que es el panel de la llamada, no en un enlace que no lleva a ningún sitio.
  {
    titulo: "Análisis",
    items: [{ to: "/evaluacion", label: "Evaluación", icon: BarChart3 }],
  },
  {
    titulo: "Configuración",
    items: [{ to: "/ajustes", label: "Ajustes", icon: Settings }],
  },
];

export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <div className="flex h-full flex-col border-r border-sidebar-border bg-sidebar">
      <div className="flex items-center gap-3 px-5 py-5">
        <BrandMark size={38} />
        <div className="min-w-0">
          <p className="truncate text-[0.95rem] font-semibold leading-tight">Copiloto</p>
          <p className="truncate text-xs text-muted-foreground">Atención al Cliente</p>
        </div>
      </div>

      <nav className="flex-1 space-y-6 overflow-y-auto px-3 pb-4">
        {SECCIONES.map((seccion, i) => (
          <div key={seccion.titulo ?? i}>
            {seccion.titulo && (
              <p className="px-3 pb-2 text-[0.65rem] font-semibold uppercase tracking-[0.09em] text-muted-foreground/70">
                {seccion.titulo}
              </p>
            )}
            <ul className="space-y-1">
              {seccion.items.map((item) => (
                <li key={item.to}>
                  {item.fase ? (
                    <span
                      className="flex cursor-not-allowed items-center gap-3 rounded-lg px-3 py-2 text-sm text-muted-foreground/60"
                      title={`Se construye en la ${item.fase}`}
                    >
                      <item.icon className="size-[1.15rem] shrink-0" />
                      <span className="flex-1 truncate">{item.label}</span>
                      <Badge variant="muted" className="px-1.5 py-0 text-[0.62rem]">
                        {item.fase}
                      </Badge>
                    </span>
                  ) : (
                    <NavLink
                      to={item.to}
                      end={item.to === "/"}
                      onClick={onNavigate}
                      className={({ isActive }) =>
                        cn(
                          "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                          isActive
                            ? "bg-gradient-to-r from-primary to-violet-500 text-white shadow-sm"
                            : "text-sidebar-foreground hover:bg-muted",
                        )
                      }
                    >
                      <item.icon className="size-[1.15rem] shrink-0" />
                      <span className="truncate">{item.label}</span>
                    </NavLink>
                  )}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>

      <div className="border-t border-sidebar-border p-3">
        <div className="rounded-lg bg-gradient-to-br from-primary/10 to-violet-500/10 p-3">
          <p className="text-xs font-semibold">Perímetro Perú</p>
          <p className="mt-1 text-[0.7rem] leading-relaxed text-muted-foreground">
            Plazos y clasificación de reclamos según la Ley 31763 (SBS).
          </p>
        </div>
      </div>
    </div>
  );
}
