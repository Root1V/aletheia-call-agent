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
