import { AlertTriangle } from "lucide-react";

import { Badge } from "@/components/ui/badge";

/**
 * Tiempo de armado del contexto previo a descolgar.
 *
 * En producción sólo aparece cuando se sale del presupuesto. El resto del
 * tiempo no dice nada que un ejecutivo pueda accionar: ocupaba un hueco
 * permanente en la barra superior con una cifra en milisegundos y un término
 * en inglés —"pre-pop"— que nadie en esa silla conoce. Cuando se pasa del
 * umbral sí es accionable, porque significa que algo se degradó y la llamada
 * va a empezar con la pantalla a medio armar.
 *
 * En desarrollo se muestra siempre: ahí el número es justo lo que se está
 * vigilando.
 */
export function ContextTiming({ buildMs, budgetMs }: { buildMs: number; budgetMs: number }) {
  const fueraDePresupuesto = buildMs > budgetMs;

  if (fueraDePresupuesto) {
    return (
      <Badge
        variant="warning"
        className="tabular"
        title={`El contexto tardó ${buildMs} ms, por encima del presupuesto de ${budgetMs} ms`}
      >
        <AlertTriangle className="size-3" />
        Contexto lento · {Math.round(buildMs)} ms
      </Badge>
    );
  }

  if (!import.meta.env.DEV) return null;

  return (
    <Badge
      variant="muted"
      className="tabular font-mono"
      title={`Armado del contexto previo a descolgar · presupuesto ${budgetMs} ms · sólo visible en desarrollo`}
    >
      contexto {buildMs} ms
    </Badge>
  );
}
