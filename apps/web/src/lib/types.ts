/**
 * Espejo en TypeScript de `packages/contracts`.
 *
 * Se escribe a mano y no se genera para mantener el frontend sin paso de build
 * extra, pero eso abre riesgo de deriva: si alguien cambia un campo en Pydantic
 * y no aquí, el error aparece en tiempo de ejecución y no de compilación.
 * `packages/contracts/tests/test_espejo_typescript.py` compara ambos lados en
 * cada ejecución de la suite: nombres de campo y anulabilidad, que es donde
 * ocurre la deriva. Existe porque ya ocurrió — `proposed_type` era obligatorio
 * en Pydantic y anulable aquí, y la llamada que se resuelve sin abrir caso
 * reventaba al publicar el evento sin que el portal se enterase.
 */

export type Speaker = "customer" | "agent";

export type AuthLevel = "no_verificado" | "parcial" | "verificado" | "fallido";

export type TransactionStatus = "pendiente" | "liquidada" | "rechazada" | "revertida";

export type Channel =
  | "app" | "web" | "pos" | "atm" | "ecommerce" | "ivr" | "agencia" | "call_center";

export type CaseType = "reclamo" | "requerimiento";

export type EmotionLabel =
  | "frustracion" | "satisfaccion" | "confusion" | "urgencia" | "neutral";

export interface AuthFactor {
  kind: string;
  passed: boolean;
  detail: string | null;
}

export interface TrustState {
  level: AuthLevel;
  factors: AuthFactor[];
  fraud_risk_score: number;
  synthetic_voice_score: number | null;
  step_up_required_for: string[];
}

export interface Merchant {
  merchant_id: string;
  display_name: string;
  legal_name: string | null;
  category: string;
  logo_url: string | null;
  district: string | null;
  city: string | null;
  country: string;
}

export interface Transaction {
  transaction_id: string;
  account_id: string;
  occurred_at: string;
  amount: string;
  currency: string;
  status: TransactionStatus;
  channel: Channel;
  /** Lo que el cliente ve en su estado de cuenta, sin traducir. */
  raw_descriptor: string;
  merchant: Merchant | null;
  device_label: string | null;
  decline_reason: string | null;
  prior_purchases_90d: number;
  is_recurring: boolean;
}

export interface DigitalJourneyEvent {
  occurred_at: string;
  channel: Channel;
  screen: string;
  action: string;
  succeeded: boolean;
  detail: string | null;
}

export interface AccountEvent {
  occurred_at: string;
  kind: string;
  summary: string;
  related_transaction_id: string | null;
  severity: string;
}

export interface Case {
  case_id: string;
  folio: string;
  case_type: CaseType;
  status: string;
  opened_at: string;
  due_at: string;
  subject: string;
  summary: string | null;
  related_transaction_id: string | null;
}

export interface IntentPrediction {
  intent: string;
  confidence: number;
  evidence: string[];
  source: string;
}

export interface ProductHolding {
  holding_id: string;
  product_code: string;
  product_name: string;
  opened_at: string;
  balance: string | null;
  credit_limit: string | null;
  currency: string;
  status: string;
  masked_number: string | null;
}

export interface Customer {
  customer_id: string;
  full_name: string;
  document_type: string;
  document_masked: string;
  segment: string;
  customer_since: string;
  birth_date: string | null;
  city: string | null;
  district: string | null;
  phone_masked: string | null;
  email_masked: string | null;
  nps: number | null;
  preferred_language: string;
  vulnerabilities: string[];
  holdings: ProductHolding[];
}

export interface CallContext {
  call_id: string;
  customer: Customer;
  trust: TrustState;
  intent: IntentPrediction;
  recent_account_events: AccountEvent[];
  digital_journey: DigitalJourneyEvent[];
  open_cases: Case[];
  relevant_transactions: Transaction[];
  focus_transaction_id: string | null;
  /** Compras ANTERIORES y liquidadas en el mismo comercio: sostienen la explicación. */
  supporting_transaction_ids: string[];
  /** Intentos POSTERIORES, normalmente rechazados: significan lo contrario. */
  related_attempt_ids: string[];
  generated_at: string;
}

export interface ContextResponse {
  context: CallContext;
  /** Cuánto tardó el servidor en armar el contexto previo a descolgar. */
  build_ms: number;
  /** Umbral contra el que juzgarlo. Viaja con la medición para que no haya dos copias. */
  budget_ms: number;
}

export interface InboundCall {
  call_id: string;
  customer_id: string;
  customer_name: string;
  segment: string;
  scenario_id: string;
  narrative: string;
}

// ── Eventos del bus de la llamada ───────────────────────────────────────────
//
// Espejo de `packages/contracts/events.py`. Sólo se declaran los que el portal
// consume hoy; los demás llegan por el mismo canal y se ignoran sin ruido.

export interface AsrPartialEvent {
  type: "asr.partial";
  call_id: string;
  seq: number;
  ts_ms: number;
  speaker: Speaker;
  turn_id: string;
  text: string;
  started_at_ms: number;
}

export interface AsrFinalEvent {
  type: "asr.final";
  call_id: string;
  seq: number;
  ts_ms: number;
  speaker: Speaker;
  turn_id: string;
  text: string;
  started_at_ms: number;
  ended_at_ms: number;
  reconciled: boolean;
}

export interface CallStartedEvent {
  type: "call.started";
  call_id: string;
  seq: number;
  ts_ms: number;
  customer_id: string;
  agent_id: string;
  ingress: string;
}

export interface CallEndedEvent {
  type: "call.ended";
  call_id: string;
  seq: number;
  ts_ms: number;
  duration_ms: number;
  reason: string;
}

export interface Citation {
  chunk_id: string;
  document: string;
  section: string | null;
  snippet: string;
  score: number | null;
}

export interface SuggestionStartedEvent {
  type: "suggestion.started";
  call_id: string;
  seq: number;
  ts_ms: number;
  suggestion_id: string;
  trigger_turn_id: string;
  speculative: boolean;
}

export interface SuggestionCompletedEvent {
  type: "suggestion.completed";
  call_id: string;
  seq: number;
  ts_ms: number;
  suggestion_id: string;
  text: string;
  citations: Citation[];
  emotion_adapted_to: EmotionLabel | null;
  /** Un guardarraíl la detuvo: sin respaldo, cifra no verificada o frase prohibida. */
  blocked: boolean;
  blocked_reason: string | null;
  latency_ms: number | null;
}

export interface DraftCase {
  case_id: string;
  folio: string;
  customer_id: string;
  case_type: CaseType;
  status: string;
  opened_at: string;
  /** Vencimiento del plazo regulatorio: 15 días hábiles bajo la Ley 31763. */
  due_at: string;
  subject: string;
  summary: string | null;
  related_transaction_id: string | null;
}

export interface CaseClassifiedEvent {
  type: "case.classified";
  call_id: string;
  seq: number;
  ts_ms: number;
  /** null cuando la llamada se resolvió sin abrir caso. */
  proposed_type: CaseType | null;
  confidence: number;
  rationale: string;
  evidence_turn_ids: string[];
  citations: Citation[];
  confirmed_by_agent: boolean | null;
  draft_case: DraftCase | null;
}

export interface StreamControlEvent {
  type: "stream.ready" | "stream.heartbeat";
  call_id?: string;
}

export type EventoConocido =
  | AsrPartialEvent
  | AsrFinalEvent
  | EmotionFrameEvent
  | CallStartedEvent
  | CallEndedEvent
  | SuggestionStartedEvent
  | SuggestionCompletedEvent
  | CaseClassifiedEvent
  | StreamControlEvent;

/**
 * Lo que llega por el WebSocket.
 *
 * El comodín existe porque el bus transporta más eventos de los que el portal
 * consume hoy, y los desconocidos debe ignorarlos sin romperse. Como ese
 * comodín acepta cualquier `type`, comparar el campo directamente no estrecha
 * el tipo: para eso está `es()`.
 */
export type CallEvent = EventoConocido | { type: string; [k: string]: unknown };

/**
 * Estrecha un evento del bus a su tipo concreto.
 *
 * El servidor valida cada evento contra `packages/contracts` antes de
 * publicarlo, así que si el `type` coincide la forma está garantizada. El
 * riesgo real no es un payload malformado sino la deriva entre estos tipos y
 * los de Pydantic.
 */
export function es<T extends EventoConocido>(ev: CallEvent, tipo: T["type"]): ev is T {
  return ev.type === tipo;
}

/** Un turno tal como lo pinta la UI. */
export interface Turno {
  turnId: string;
  speaker: Speaker;
  text: string;
  isFinal: boolean;
  startedAtMs: number;
  /** Orden de llegada: mantiene estable la posición en pantalla. */
  seq: number;
}

export interface EmotionFrameEvent {
  type: "emotion.frame";
  call_id: string;
  seq: number;
  ts_ms: number;
  speaker: "customer";
  /** Parcial a propósito: sólo las dimensiones que hay evidencia para sostener. */
  scores: Partial<Record<"frustracion" | "satisfaccion" | "confusion" | "urgencia" | "neutral", number>>;
  /** null cuando no se ha medido. No es lo mismo que "neutral". */
  valence: number | null;
  arousal: number;
  confidence: number;
  window_ms: number;
  contributions: Record<string, number>;
}

export interface EstadoEmocional {
  arousal: number;
  scores: Record<string, number>;
  confidence: number;
  contributions: Record<string, number>;
  tsMs: number;
}

/**
 * La sugerencia activa del copiloto.
 *
 * Hay como mucho una a la vez, y es una decisión de producto, no una
 * limitación: una tarjeta nueva mientras el ejecutivo lee la anterior hace que
 * deje de leerlas, y una herramienta que se deja de leer está desinstalada
 * aunque siga corriendo.
 */
export interface SugerenciaViva {
  id: string;
  /** Mientras se redacta y se verifica no hay texto que mostrar. */
  estado: "redactando" | "lista" | "bloqueada";
  texto: string;
  citas: Citation[];
  emocion: EmotionLabel | null;
  motivoDeBloqueo: string | null;
  latenciaMs: number | null;
  /** Qué hizo el ejecutivo. Se guarda para no volver a mostrarla tras descartarla. */
  resuelta: boolean;
}

/** La clasificación propuesta, tal como la pinta el portal. */
export interface ClasificacionViva {
  tipo: CaseType | null;
  confianza: number;
  justificacion: string;
  turnosDeEvidencia: string[];
  borrador: DraftCase | null;
  /** Qué hizo el ejecutivo: confirmar, corregir, o nada todavía. */
  decision: "pendiente" | "confirmada" | "corregida";
}
