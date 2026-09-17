import { useMutation } from "@tanstack/react-query";
import { Check, FileText, Loader2, Pencil, ShieldAlert, TableProperties, X } from "lucide-react";
import { useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { endpoints } from "@/lib/api/endpoints";
import type { EmotionLabel, SugerenciaViva } from "@/lib/types";

const TONO: Record<EmotionLabel, string> = {
  frustracion: "adaptada a un cliente molesto",
  confusion: "adaptada a un cliente que no entiende",
  urgencia: "adaptada a un cliente con prisa",
  satisfaccion: "adaptada a un cliente receptivo",
  neutral: "sin adaptación de tono",
};

/**
 * La tarjeta del copiloto: una frase para decir en voz alta, con su fuente.
 *
 * Tres decisiones que son de producto, no de estilo:
 *
 * 1. **No hay texto en streaming.** El primer token llega a los ~90 ms, pero la
 *    verificación de cifras se hace sobre el texto completo. Una comisión
 *    equivocada que parpadea medio segundo en pantalla ya la puede haber leído
 *    el ejecutivo en voz alta, y entonces el guardarraíl no sirvió de nada. Se
 *    gana latencia percibida anunciando la tarjeta, no arriesgando el número.
 *
 * 2. **Una bloqueada se muestra igual, con su motivo.** Un hueco en blanco es
 *    indistinguible de un fallo, y el ejecutivo se queda esperando. Decir "me
 *    callé porque no pude verificar la cifra" mantiene la confianza.
 *
 * 3. **Usar / Editar / Descartar.** Es la señal de calidad más valiosa que
 *    produce el sistema y la única que no se puede reconstruir después: ninguna
 *    grabación distingue una sugerencia usada de una ignorada.
 *
 * El estado del editor es local y se descarta al llegar una sugerencia nueva.
 * Eso lo resuelve la `key` del componente en el workspace, no un efecto que
 * limpie el borrador: remontar es la forma que React tiene de decir "esto es
 * otra cosa", y evita la cascada de renders de un `setState` dentro de un
 * efecto.
 */
export function CopilotSuggestion({
  callId,
  sugerencia,
  onResolver,
}: {
  callId: string;
  sugerencia: SugerenciaViva | null;
  onResolver: (id: string) => void;
}) {
  const [editando, setEditando] = useState(false);
  const [borrador, setBorrador] = useState("");
  const areaRef = useRef<HTMLTextAreaElement>(null);

  const feedback = useMutation({
    mutationFn: ({ accion, texto }: { accion: "used" | "edited" | "dismissed"; texto?: string }) =>
      endpoints.suggestionFeedback(callId, sugerencia!.id, accion, texto),
  });

  if (!sugerencia || sugerencia.resuelta) {
    return (
      <Card className="border-dashed">
        <CardHeader>
          <CardTitle>Copiloto</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm leading-relaxed text-muted-foreground">
            La sugerencia aparece cuando el cliente termina de hablar. No se genera sobre
            asentimientos ni sobre el turno del ejecutivo.
          </p>
        </CardContent>
      </Card>
    );
  }

  const resolver = (accion: "used" | "edited" | "dismissed", texto?: string) => {
    feedback.mutate({ accion, texto });
    onResolver(sugerencia.id);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Copiloto</CardTitle>
        <div className="flex items-center gap-1.5">
          {sugerencia.emocion && sugerencia.estado === "lista" && (
            <Badge variant="muted" title={TONO[sugerencia.emocion]}>
              {sugerencia.emocion}
            </Badge>
          )}
          {sugerencia.latenciaMs !== null && import.meta.env.DEV && (
            <Badge variant="muted" className="tabular font-mono">
              {sugerencia.latenciaMs} ms
            </Badge>
          )}
        </div>
      </CardHeader>

      <CardContent className="space-y-3">
        {sugerencia.estado === "redactando" && (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" />
            Redactando y verificando contra el tarifario…
          </p>
        )}

        {sugerencia.estado === "bloqueada" && (
          <div className="flex gap-2 rounded-md bg-warning-soft p-3">
            <ShieldAlert className="mt-0.5 size-4 shrink-0 text-warning" />
            <div className="space-y-1">
              <p className="text-sm font-medium text-warning">No se muestra la sugerencia</p>
              <p className="text-sm leading-relaxed text-muted-foreground">
                {sugerencia.motivoDeBloqueo ?? "Un guardarraíl la detuvo."}
              </p>
            </div>
          </div>
        )}

        {sugerencia.estado === "lista" && !editando && (
          <blockquote className="border-l-2 border-primary pl-3 text-[15px] leading-relaxed">
            {sugerencia.texto}
          </blockquote>
        )}

        {sugerencia.estado === "lista" && editando && (
          <textarea
            ref={areaRef}
            value={borrador}
            onChange={(e) => setBorrador(e.target.value)}
            rows={4}
            className="w-full resize-y rounded-md border border-border bg-background p-2 text-[15px] leading-relaxed outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
        )}

        {sugerencia.estado === "lista" && sugerencia.citas.length > 0 && (
          <ul className="space-y-1">
            {sugerencia.citas.map((c) => (
              <li
                key={c.chunk_id}
                className="flex items-start gap-1.5 text-xs text-muted-foreground"
                title={c.snippet}
              >
                <FileText className="mt-0.5 size-3 shrink-0" />
                <span>
                  {c.document}
                  {c.section && ` § ${c.section}`}
                </span>
              </li>
            ))}
          </ul>
        )}

        {/*
          Sin citas NO es un error: es el caso más frecuente del flujo de
          reclamos, donde la frase se construye entera con el comercio real, la
          fecha y las compras previas de esta llamada. Decirlo importa: es el
          ejecutivo quien responde si el cliente pregunta de dónde sale el dato,
          y una referencia al tarifario bajo una frase que no debe nada al
          tarifario le haría creer que tiene un respaldo que no tiene.
        */}
        {sugerencia.estado === "lista" && sugerencia.citas.length === 0 && (
          <p className="flex items-start gap-1.5 text-xs text-muted-foreground">
            <TableProperties className="mt-0.5 size-3 shrink-0" />
            Según los datos de esta llamada, sin respaldo en la base de conocimiento.
          </p>
        )}

        <div className="flex flex-wrap gap-2">
          {sugerencia.estado === "lista" && !editando && (
            <>
              <Button size="sm" onClick={() => resolver("used")}>
                <Check />
                Usar
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  setBorrador(sugerencia.texto);
                  setEditando(true);
                  // El foco va al final del texto, no al principio: quien edita
                  // una sugerencia casi siempre añade o corrige el final.
                  requestAnimationFrame(() => {
                    const el = areaRef.current;
                    if (!el) return;
                    el.focus();
                    el.setSelectionRange(el.value.length, el.value.length);
                  });
                }}
              >
                <Pencil />
                Editar
              </Button>
            </>
          )}

          {sugerencia.estado === "lista" && editando && (
            <Button size="sm" onClick={() => resolver("edited", borrador)}>
              <Check />
              Usar mi versión
            </Button>
          )}

          <Button size="sm" variant="ghost" onClick={() => resolver("dismissed")}>
            <X />
            Descartar
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
