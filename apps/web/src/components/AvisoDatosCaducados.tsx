import { AlertTriangle } from "lucide-react";

import { Card } from "@/components/ui/card";

/**
 * Los escenarios colocan sus eventos en relación al momento de la siembra —"el
 * cargo fue hace veinte horas"— y el contexto de llamada sólo mira las últimas
 * 72 horas. Pasado ese plazo, los paneles aparecen VACÍOS sin ningún error.
 *
 * Ese es el peor modo de fallo posible en una demostración: parece que el
 * producto no funciona cuando lo único que caducó son los datos de prueba.
 * Este aviso convierte una degradación silenciosa en una instrucción.
 */
const HORAS_AVISO = 40;
const HORAS_CADUCADO = 72;

export function AvisoDatosCaducados({ horas }: { horas: number | null }) {
  if (horas === null || horas < HORAS_AVISO) return null;

  const caducado = horas >= HORAS_CADUCADO;
  const dias = Math.floor(horas / 24);
  const antiguedad = dias >= 1 ? `${dias} día${dias > 1 ? "s" : ""}` : `${Math.round(horas)} horas`;

  return (
    <Card
      className={
        caducado ? "border-danger/40 bg-danger-soft/40" : "border-warning/40 bg-warning-soft/40"
      }
    >
      <div className="flex items-start gap-3 p-4">
        <AlertTriangle
          className={`mt-0.5 size-5 shrink-0 ${caducado ? "text-danger" : "text-warning"}`}
        />
        <div className="space-y-1 text-sm">
          <p className="font-medium">
            {caducado
              ? `Los datos de demostración caducaron hace ${antiguedad}`
              : `Los datos de demostración tienen ${antiguedad}`}
          </p>
          <p className="text-muted-foreground">
            {caducado
              ? "Los eventos que arman el contexto salieron de la ventana de 72 horas, así que los paneles aparecerán vacíos. No es un fallo del sistema."
              : "Dentro de poco saldrán de la ventana de 72 horas que usa el contexto de llamada."}{" "}
            Regenéralos con <span className="font-mono text-foreground">make seed</span>.
          </p>
        </div>
      </div>
    </Card>
  );
}
