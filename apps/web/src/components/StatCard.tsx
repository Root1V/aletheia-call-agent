import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

/**
 * Tarjeta de métrica.
 *
 * Sin variación "vs. mes anterior" a propósito: el sistema no lleva todavía
 * series históricas, y un "+18%" inventado para que la tarjeta se vea completa
 * es exactamente el tipo de dato que alguien termina citando en una reunión.
 * `nota` deja decir algo verdadero en ese espacio.
 */
export function StatCard({
  icono: Icono,
  valor,
  etiqueta,
  nota,
  tono = "default",
}: {
  icono: React.ComponentType<{ className?: string }>;
  valor: string | number;
  etiqueta: string;
  nota?: string;
  tono?: "default" | "warning" | "danger" | "success";
}) {
  const tonos = {
    default: "bg-primary-soft text-primary",
    warning: "bg-warning-soft text-warning",
    danger: "bg-danger-soft text-danger",
    success: "bg-success-soft text-success",
  } as const;

  return (
    <Card className="p-4">
      <div className="flex items-start gap-3">
        <span className={cn("grid size-10 shrink-0 place-items-center rounded-lg", tonos[tono])}>
          <Icono className="size-5" />
        </span>
        <div className="min-w-0">
          <p className="tabular text-2xl font-semibold leading-tight">{valor}</p>
          <p className="truncate text-sm text-muted-foreground">{etiqueta}</p>
          {nota && <p className="mt-1 text-xs text-muted-foreground/80">{nota}</p>}
        </div>
      </div>
    </Card>
  );
}
