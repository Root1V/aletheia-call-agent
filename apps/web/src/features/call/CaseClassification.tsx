import { Check, FileWarning, Pencil, ScrollText } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ClasificacionViva } from "@/lib/types";

/** Días hábiles restantes, sobre el calendario local. Sin feriados: deuda declarada. */
function diasHabilesHasta(iso: string): number {
  const fin = new Date(iso);
  const actual = new Date();
  let dias = 0;
  while (actual < fin) {
    actual.setDate(actual.getDate() + 1);
    const d = actual.getDay();
    if (d !== 0 && d !== 6) dias += 1;
  }
  return dias;
}

const FECHA = new Intl.DateTimeFormat("es-PE", {
  day: "2-digit",
  month: "2-digit",
  timeZone: "America/Lima",
});

/**
 * La clasificación del caso bajo la Ley 31763, propuesta y NO decidida.
 *
 * El botón dice "Confirmar" y no "Guardar" a propósito: lo que el ejecutivo
 * hace aquí es asumir una decisión con consecuencia regulatoria, y la interfaz
 * no puede hacerla parecer un trámite. Clasificar un reclamo como requerimiento
 * priva al usuario del plazo de quince días hábiles y de la vía de escalamiento
 * a la SBS.
 *
 * Por eso también se muestra siempre la justificación y la regla: una propuesta
 * que no se puede contrastar se confirma sin leer, que es el automatismo que
 * este control existe para evitar.
 */
export function CaseClassification({
  clasificacion,
  onDecidir,
}: {
  clasificacion: ClasificacionViva | null;
  onDecidir: (decision: "confirmada" | "corregida") => void;
}) {
  if (!clasificacion) {
    return (
      <Card className="border-dashed">
        <CardHeader>
          <CardTitle>Clasificación del caso</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm leading-relaxed text-muted-foreground">
            Al terminar la llamada se propone si corresponde un reclamo o un requerimiento bajo la
            Ley 31763, con su justificación y la evidencia de la conversación.
          </p>
        </CardContent>
      </Card>
    );
  }

  const { tipo, confianza, justificacion, borrador, decision } = clasificacion;
  const resuelta = tipo === null;
  const dias = borrador ? diasHabilesHasta(borrador.due_at) : null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Clasificación del caso</CardTitle>
        <div className="flex items-center gap-1.5">
          <Badge variant={resuelta ? "muted" : tipo === "reclamo" ? "warning" : "default"}>
            {resuelta ? "sin caso" : tipo}
          </Badge>
          <Badge variant="muted" className="tabular">
            {Math.round(confianza * 100)}%
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="space-y-3">
        <p className="text-sm leading-relaxed">{justificacion}</p>

        {resuelta && (
          <p className="text-xs leading-relaxed text-muted-foreground">
            El cliente retiró la observación durante la llamada. Si aun así pide dejar constancia,
            corrija esta propuesta: el reclamo se registra igual.
          </p>
        )}

        {borrador && (
          <div className="space-y-1.5 rounded-md bg-muted p-3">
            <p className="flex items-center gap-1.5 text-sm font-medium">
              <ScrollText className="size-4 shrink-0" />
              {borrador.subject}
            </p>
            <p className="text-xs text-muted-foreground">
              Folio provisional <span className="font-mono">{borrador.folio}</span> · el definitivo
              lo emite el sistema de casos al registrar
            </p>
            {dias !== null && (
              <p className="flex items-center gap-1.5 text-xs">
                <FileWarning className="size-3 shrink-0 text-warning" />
                <span className={dias <= 3 ? "font-medium text-warning" : "text-muted-foreground"}>
                  Plazo de respuesta: {dias} días hábiles ({FECHA.format(new Date(borrador.due_at))})
                </span>
              </p>
            )}
          </div>
        )}

        {/*
          El registro efectivo del caso es una acción ejecutable (RF-16), fuera
          del alcance actual por decisión. Se prepara el borrador y se declara;
          un botón que dijera "Registrar" prometería algo que el sistema no hace
          todavía, y descubrirlo con el cliente al teléfono es la peor forma.
        */}
        {decision === "pendiente" ? (
          <div className="flex flex-wrap gap-2">
            <Button size="sm" onClick={() => onDecidir("confirmada")}>
              <Check />
              Confirmar
            </Button>
            <Button size="sm" variant="outline" onClick={() => onDecidir("corregida")}>
              <Pencil />
              Corregir
            </Button>
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">
            {decision === "confirmada"
              ? "Confirmada por usted. Queda en el registro de auditoría."
              : "Marcada para corregir. Regístrela en el sistema de casos con el tipo correcto."}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
