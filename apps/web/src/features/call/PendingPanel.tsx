import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

/**
 * Zona del workspace todavía no construida.
 *
 * Se muestra explícitamente en lugar de dejar un hueco o, peor, de rellenarlo
 * con datos falsos que parezcan reales. En una demo para un comité, una
 * transcripción simulada indistinguible de una real es la forma más rápida de
 * perder la confianza cuando alguien pregunta de dónde salió.
 */
export function PendingPanel({
  titulo,
  fase,
  children,
}: {
  titulo: string;
  fase: string;
  children: React.ReactNode;
}) {
  return (
    <Card className="border-dashed">
      <CardHeader>
        <CardTitle>{titulo}</CardTitle>
        <Badge variant="muted">{fase}</Badge>
      </CardHeader>
      <CardContent>
        <p className="text-sm leading-relaxed text-muted-foreground">{children}</p>
      </CardContent>
    </Card>
  );
}
