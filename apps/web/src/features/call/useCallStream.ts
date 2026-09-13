import { useCallback, useEffect, useRef, useState } from "react";

import { tokenStore } from "@/lib/api/client";
import { es } from "@/lib/types";
import type {
  AsrFinalEvent,
  AsrPartialEvent,
  CallEvent,
  CallStartedEvent,
  EmotionFrameEvent,
  EstadoEmocional,
  Turno,
} from "@/lib/types";

type Estado = "conectando" | "en_vivo" | "terminada" | "sin_conexion";

const RECONEXION_MS = [500, 1000, 2000, 5000, 10000];

/**
 * Transcripción en vivo de una llamada.
 *
 * El token viaja en el campo de subprotocolos y no en la URL: la API de
 * WebSocket del navegador no admite cabeceras, y las URLs terminan en los logs
 * de acceso, en los del proxy y en el historial, donde un token de nueve horas
 * es una credencial filtrada.
 */
export function useCallStream(callId: string | undefined) {
  const [turnos, setTurnos] = useState<Turno[]>([]);
  const [emocion, setEmocion] = useState<EstadoEmocional | null>(null);
  const [estado, setEstado] = useState<Estado>("conectando");
  const wsRef = useRef<WebSocket | null>(null);
  const intentoRef = useRef(0);
  const vivoRef = useRef(true);
  // Si ya se terminó de recibir el historial. Distingue "reconstruyendo lo que
  // pasó" de "esto está ocurriendo ahora", que es lo que la insignia comunica.
  const enVivoRef = useRef(false);

  const aplicar = useCallback((ev: CallEvent) => {
    // Una llamada nueva descarta lo anterior.
    //
    // El identificador de llamada de un escenario es determinista, así que un
    // historial puede contener más de una reproducción. Sin este corte, el
    // portal pinta las dos y cada turno aparece por duplicado. Anclar en el
    // último inicio hace que la vista sea correcta aunque el bus arrastre
    // restos de una ejecución anterior.
    if (es<CallStartedEvent>(ev, "call.started")) {
      setTurnos([]);
      setEmocion(null);
      // El estado sólo se toca si ya estábamos en vivo: entonces este inicio
      // es una llamada nueva sobre la misma conexión y hay que salir de
      // "terminada". Durante la reconstrucción del historial se deja como
      // está, o la insignia se quedaría en "Conectando…" para siempre.
      if (enVivoRef.current) setEstado("en_vivo");
      return;
    }

    if (es<AsrPartialEvent>(ev, "asr.partial") || es<AsrFinalEvent>(ev, "asr.final")) {
      const e: AsrPartialEvent | AsrFinalEvent = ev;
      setTurnos((previos) => {
        const i = previos.findIndex((t) => t.turnId === e.turn_id);
        const turno: Turno = {
          turnId: e.turn_id,
          speaker: e.speaker,
          text: e.text,
          isFinal: e.type === "asr.final",
          startedAtMs: e.started_at_ms,
          seq: i >= 0 ? previos[i]!.seq : e.seq,
        };
        if (i < 0) return [...previos, turno];
        // El parcial se SUSTITUYE, no se añade: el reconocedor reenvía la
        // hipótesis completa del turno cada vez, no sólo lo nuevo. Concatenar
        // produciría "Buenos Buenos días Buenos días, tengo...".
        const copia = [...previos];
        copia[i] = turno;
        return copia;
      });
      return;
    }
    if (es<EmotionFrameEvent>(ev, "emotion.frame")) {
      const e = ev;
      setEmocion({
        arousal: e.arousal,
        scores: e.scores as Record<string, number>,
        confidence: e.confidence,
        contributions: e.contributions,
        tsMs: e.ts_ms,
      });
      return;
    }
    if (ev.type === "call.ended") setEstado("terminada");
  }, []);

  useEffect(() => {
    if (!callId) return;
    vivoRef.current = true;
    let temporizador: number | undefined;

    const conectar = () => {
      if (!vivoRef.current) return;
      const token = tokenStore.get();
      if (!token) {
        setEstado("sin_conexion");
        return;
      }

      const proto = location.protocol === "https:" ? "wss" : "ws";
      const ws = new WebSocket(`${proto}://${location.host}/ws/calls/${callId}`, [
        "cea.v1",
        `bearer.${token}`,
      ]);
      wsRef.current = ws;

      ws.onopen = () => {
        intentoRef.current = 0;
        enVivoRef.current = false;
        setEstado("conectando");
      };

      ws.onmessage = (msg) => {
        const ev = JSON.parse(msg.data as string) as CallEvent;
        // El servidor manda todo el historial y luego avisa. Hasta entonces la
        // UI está reconstruyendo, no "en vivo".
        if (ev.type === "stream.ready") {
          enVivoRef.current = true;
          setEstado("en_vivo");
          return;
        }
        if (ev.type === "stream.heartbeat") return;
        aplicar(ev);
      };

      ws.onclose = () => {
        if (!vivoRef.current) return;
        setEstado("sin_conexion");
        const espera = RECONEXION_MS[Math.min(intentoRef.current, RECONEXION_MS.length - 1)]!;
        intentoRef.current += 1;
        // Al reconectar se vuelve a pedir el historial completo y el estado se
        // reconstruye desde cero. Una caída de red no puede dejar al ejecutivo
        // mirando una transcripción incompleta sin saberlo.
        temporizador = window.setTimeout(conectar, espera);
      };
    };

    conectar();

    return () => {
      vivoRef.current = false;
      window.clearTimeout(temporizador);
      wsRef.current?.close();
      setTurnos([]);
      setEmocion(null);
    };
  }, [callId, aplicar]);

  return { turnos, emocion, estado };
}
