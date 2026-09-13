import { Radio, WifiOff } from "lucide-react";
import { useEffect, useRef } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { Turno } from "@/lib/types";

/**
 * Zona 3: la conversación en vivo.
 *
 * Los turnos aún abiertos se pintan atenuados y en cursiva. Distinguir lo
 * provisional de lo consolidado no es un adorno: el texto parcial cambia
 * mientras la persona habla, y un ejecutivo que lea en voz alta una hipótesis
 * que todavía puede corregirse le está diciendo al cliente algo que el sistema
 * aún no afirma.
 */
export function LiveTranscript({
  turnos,
  estado,
}: {
  turnos: Turno[];
  estado: "conectando" | "en_vivo" | "terminada" | "sin_conexion";
}) {
  const finRef = useRef<HTMLDivElement>(null);
  const contenedorRef = useRef<HTMLDivElement>(null);
  // Si el ejecutivo está al final, la vista sigue la conversación; si subió a
  // releer algo, se queda donde está.
  const seguirRef = useRef(true);

  // La decisión se toma en el evento de scroll, no dentro del efecto.
  //
  // Calcularla después de renderizar mide el contenedor cuando la burbuja
  // nueva YA está en el DOM: la distancia al final es entonces la altura de
  // esa burbuja, supera el umbral, y la vista deja de seguir la conversación
  // exactamente a partir del segundo turno.
  const alHacerScroll = () => {
    const c = contenedorRef.current;
    if (!c) return;
    seguirRef.current = c.scrollHeight - c.scrollTop - c.clientHeight < 80;
  };

  useEffect(() => {
    if (!seguirRef.current) return;
    // Salto instantáneo, no animado.
    //
    // Un desplazamiento suave emite eventos de scroll durante toda su
    // animación, y el manejador de arriba los lee como "el usuario subió":
    // el propio auto-scroll se desactivaba solo a partir del segundo turno.
    // Además, en una transcripción que crece cada pocos segundos la animación
    // es ruido visual mientras el ejecutivo intenta leer.
    finRef.current?.scrollIntoView({ behavior: "auto", block: "end" });
  }, [turnos]);

  const ordenados = [...turnos].sort((a, b) => a.seq - b.seq);

  return (
    <Card className="flex max-h-[32rem] flex-col">
      <CardHeader>
        <CardTitle>Conversación en vivo</CardTitle>
        <EstadoBadge estado={estado} />
      </CardHeader>

      <div
        ref={contenedorRef}
        onScroll={alHacerScroll}
        className="flex-1 space-y-3 overflow-y-auto p-4"
      >
        {ordenados.length === 0 ? (
          <p className="py-10 text-center text-sm text-muted-foreground">
            {estado === "sin_conexion"
              ? "Sin conexión con el servidor de la llamada."
              : "Esperando audio…"}
          </p>
        ) : (
          ordenados.map((t) => <Burbuja key={t.turnId} turno={t} />)
        )}
        <div ref={finRef} />
      </div>
    </Card>
  );
}

function Burbuja({ turno }: { turno: Turno }) {
  const esCliente = turno.speaker === "customer";
  return (
    <div className={cn("flex", esCliente ? "justify-start" : "justify-end")}>
      <div className={cn("max-w-[85%] space-y-1", esCliente ? "items-start" : "items-end")}>
        <span
          className={cn(
            "block text-[0.65rem] font-semibold uppercase tracking-wider text-muted-foreground",
            !esCliente && "text-right",
          )}
        >
          {esCliente ? "Cliente" : "Ejecutivo"}
        </span>
        <p
          className={cn(
            "rounded-lg px-3 py-2 text-sm leading-relaxed",
            esCliente
              ? "rounded-tl-sm bg-muted text-foreground"
              : "rounded-tr-sm bg-primary-soft text-foreground",
            // Lo provisional se ve provisional.
            !turno.isFinal && "italic text-muted-foreground",
          )}
        >
          {turno.text}
        </p>
      </div>
    </div>
  );
}

function EstadoBadge({ estado }: { estado: string }) {
  if (estado === "en_vivo") {
    return (
      <Badge variant="success">
        <Radio className="size-3 animate-pulse" />
        En vivo
      </Badge>
    );
  }
  if (estado === "terminada") return <Badge variant="muted">Llamada terminada</Badge>;
  if (estado === "sin_conexion") {
    return (
      <Badge variant="danger">
        <WifiOff className="size-3" />
        Reconectando…
      </Badge>
    );
  }
  return <Badge variant="muted">Conectando…</Badge>;
}
