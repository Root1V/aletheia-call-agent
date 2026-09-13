/**
 * Espejo en TypeScript de `packages/contracts`.
 *
 * Se escribe a mano y no se genera para mantener el frontend sin paso de build
 * extra, pero eso abre riesgo de deriva: si alguien cambia un campo en Pydantic
 * y no aquí, el error aparece en tiempo de ejecución y no de compilación.
 * `npm run check:contracts` compara ambos lados contra el JSON Schema que
 * publica la API y falla si divergen.
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
  build_ms: number;
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

export interface StreamControlEvent {
  type: "stream.ready" | "stream.heartbeat";
  call_id?: string;
}

export type CallEvent =
  | AsrPartialEvent
  | AsrFinalEvent
  | CallStartedEvent
  | CallEndedEvent
  | StreamControlEvent
  | { type: string; [k: string]: unknown };

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
