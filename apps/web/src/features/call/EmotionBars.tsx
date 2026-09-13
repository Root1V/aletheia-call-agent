import { Info } from "lucide-react";
import { useEffect, useRef } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import type { EstadoEmocional } from "@/lib/types";

/** Por debajo de esto la señal es demasiado pobre para afirmar nada. */
const CONFIANZA_MINIMA = 0.35;

const ETIQUETAS: Record<string, string> = {
  frustracion: "Frustración",
  urgencia: "Urgencia",
};

/**
 * Dimensiones que la señal prosódica NO sostiene.
 *
 * Se listan explícitamente en lugar de omitirlas en silencio. Alguien que
 * conozca el plan las va a buscar, y decir "falta el modelo acústico" es mejor
 * que dejar un hueco que parezca un olvido — o, peor, pintarlas a cero, que se
 * leería como "el cliente no está satisfecho" cuando en realidad nadie lo ha
 * medido.
 */
const PENDIENTES = ["Satisfacción", "Confusión", "Valencia"];

export function EmotionBars({ estado }: { estado: EstadoEmocional | null }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  // El objetivo vive en una ref y no en el estado de React: el canvas se anima
  // a 60 fps y provocar un render por fotograma es justamente lo que hay que
  // evitar.
  const objetivoRef = useRef<EstadoEmocional | null>(null);

  // La ref se sincroniza en un efecto, no durante el render. Con renderizado
  // concurrente un render puede descartarse, y escribir ahí dejaría la ref con
  // un valor que nunca llegó a mostrarse.
  useEffect(() => {
    objetivoRef.current = estado;
  }, [estado]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Los colores se leen de las variables CSS, no se escriben aquí.
    //
    // Es lo que mantiene el canvas sincronizado con el tema: si los tonos
    // vivieran en este archivo, el modo oscuro y un rebranding tendrían que
    // tocarse en dos sitios y acabarían divergiendo.
    const leerColor = (nombre: string) =>
      getComputedStyle(document.documentElement).getPropertyValue(nombre).trim();

    const actuales = new Map<string, number>();
    let raf = 0;

    const dibujar = () => {
      const estadoActual = objetivoRef.current;
      const dpr = window.devicePixelRatio || 1;
      const ancho = canvas.clientWidth;
      const alto = canvas.clientHeight;
      if (canvas.width !== ancho * dpr || canvas.height !== alto * dpr) {
        canvas.width = ancho * dpr;
        canvas.height = alto * dpr;
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, ancho, alto);

      const fiable = (estadoActual?.confidence ?? 0) >= CONFIANZA_MINIMA;
      const claves = Object.keys(ETIQUETAS);
      const altoFila = alto / claves.length;

      claves.forEach((clave, i) => {
        const destino = fiable ? (estadoActual?.scores[clave] ?? 0) : 0;
        // Interpolación hacia el objetivo: los datos llegan a 2 Hz y sin esto
        // las barras saltarían dos veces por segundo en vez de moverse.
        const previo = actuales.get(clave) ?? 0;
        const valor = previo + (destino - previo) * 0.12;
        actuales.set(clave, valor);

        const y = i * altoFila + altoFila * 0.32;
        const h = altoFila * 0.34;
        const xEtiqueta = 96;
        const anchoPista = ancho - xEtiqueta - 44;

        ctx.fillStyle = leerColor("--muted-foreground");
        ctx.font = "500 12px ui-sans-serif, system-ui, sans-serif";
        ctx.textBaseline = "middle";
        ctx.fillText(ETIQUETAS[clave]!, 0, y + h / 2);

        ctx.fillStyle = leerColor("--border");
        redondeado(ctx, xEtiqueta, y, anchoPista, h, h / 2);
        ctx.fill();

        if (fiable && valor > 0.005) {
          // Verde bajo, ámbar medio, rojo alto: el color refuerza la magnitud
          // para que se lea de un vistazo sin tener que interpretar la barra.
          ctx.fillStyle = leerColor(
            valor > 0.66 ? "--danger" : valor > 0.4 ? "--warning" : "--success",
          );
          redondeado(ctx, xEtiqueta, y, Math.max(h, anchoPista * valor), h, h / 2);
          ctx.fill();
        }

        ctx.fillStyle = leerColor(fiable ? "--foreground" : "--muted-foreground");
        ctx.font = "600 12px ui-monospace, monospace";
        ctx.fillText(fiable ? `${Math.round(valor * 100)}%` : "—", ancho - 36, y + h / 2);
      });

      raf = requestAnimationFrame(dibujar);
    };

    raf = requestAnimationFrame(dibujar);
    return () => cancelAnimationFrame(raf);
  }, []);

  const fiable = (estado?.confidence ?? 0) >= CONFIANZA_MINIMA;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Emoción del cliente</CardTitle>
        {estado === null ? (
          <Badge variant="muted">Sin datos</Badge>
        ) : fiable ? (
          <Badge variant="muted">activación {estado.arousal.toFixed(2)}</Badge>
        ) : (
          <Badge variant="muted" title="El cliente no está hablando o la señal es pobre">
            Señal insuficiente
          </Badge>
        )}
      </CardHeader>

      <div className="p-4">
        <canvas ref={canvasRef} className="h-20 w-full" />

        <div className="mt-3 flex items-start gap-2 border-t border-border pt-3">
          <Info className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" />
          <p className="text-[0.7rem] leading-relaxed text-muted-foreground">
            Mide el <span className="font-medium text-foreground">cambio</span> respecto a la
            propia voz del cliente al inicio de la llamada —energía, tono, ritmo e
            interrupciones—, no su estado absoluto: quien entra alterado y sigue igual marca
            neutro, y lo que se detecta es que se caliente o se calme.{" "}
            <span className="font-medium text-foreground">{PENDIENTES.join(", ")}</span> requieren
            un modelo acústico validado para español, todavía sin elegir: la prosodia sola no
            distingue alegría de enfado, porque ambas suenan con energía y tono altos.
          </p>
        </div>
      </div>
    </Card>
  );
}

function redondeado(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number,
) {
  ctx.beginPath();
  ctx.roundRect(x, y, w, h, r);
}
