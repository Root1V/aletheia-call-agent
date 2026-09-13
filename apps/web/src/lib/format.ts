/**
 * Formato para el perímetro peruano.
 *
 * La zona horaria se fija a America/Lima y no se deja al navegador: el
 * ejecutivo y el cliente hablan en hora de Lima, y un portal que muestre otra
 * cosa porque la laptop está en otro huso genera exactamente la confusión que
 * el panel existe para evitar.
 */

const LIMA = "America/Lima";

/**
 * El formato se arma desde las partes en lugar de usar `format()` directo.
 *
 * `es-PE` ignora el `2-digit` pedido para día y mes y devuelve "4/9" en vez de
 * "04/09". En una lista densa de movimientos eso rompe la alineación de la
 * columna y, peor, produce dos formatos distintos en la misma pantalla: el
 * backend ya entrega "10/09" en la evidencia del motivo. Para el ejecutivo que
 * compara ambos paneles, la misma fecha escrita de dos formas parece dos
 * fechas.
 */
const partesFechaHora = new Intl.DateTimeFormat("es-PE", {
  timeZone: LIMA,
  day: "2-digit",
  month: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

function pad(v: string): string {
  return v.padStart(2, "0");
}

function partes(fmt: Intl.DateTimeFormat, d: Date): Record<string, string> {
  return Object.fromEntries(fmt.formatToParts(d).map((p) => [p.type, p.value]));
}

const soles = new Intl.NumberFormat("es-PE", {
  style: "currency",
  currency: "PEN",
  minimumFractionDigits: 2,
});

export function fmtFechaHora(iso: string): string {
  const p = partes(partesFechaHora, new Date(iso));
  return `${pad(p.day!)}/${pad(p.month!)} ${pad(p.hour!)}:${pad(p.minute!)}`;
}

export function fmtFecha(iso: string): string {
  const p = partes(partesFechaHora, new Date(iso));
  return `${pad(p.day!)}/${pad(p.month!)}`;
}

export function fmtMonto(amount: string, currency = "PEN"): string {
  const n = Number(amount);
  if (currency === "PEN") return soles.format(n);
  return new Intl.NumberFormat("es-PE", { style: "currency", currency }).format(n);
}

/** "hace 3 h", "hace 2 d". Más útil que la fecha absoluta para eventos recientes. */
export function hace(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  const min = Math.round(ms / 60000);
  if (min < 1) return "recién";
  if (min < 60) return `hace ${min} min`;
  const h = Math.round(min / 60);
  if (h < 24) return `hace ${h} h`;
  return `hace ${Math.round(h / 24)} d`;
}

/** Días hábiles que faltan hasta una fecha. Negativo si el plazo ya venció. */
export function diasHabilesHasta(iso: string): number {
  const objetivo = new Date(iso);
  const hoy = new Date();
  const signo = objetivo < hoy ? -1 : 1;
  const [desde, hasta] = signo > 0 ? [hoy, objetivo] : [objetivo, hoy];

  let dias = 0;
  const cursor = new Date(desde);
  while (cursor < hasta) {
    cursor.setDate(cursor.getDate() + 1);
    const d = cursor.getDay();
    if (d !== 0 && d !== 6) dias += 1;
  }
  return signo * dias;
}
