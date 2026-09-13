import type { ContextResponse, InboundCall } from "@/lib/types";

import { api } from "./client";

export interface Agent {
  agent_id: string;
  username: string;
  name: string;
  roles: string[];
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  agent: Agent;
}

export interface Health {
  status: string;
  auth_mode: string;
  entorno: string;
  postgres: { ok: boolean; escenarios?: number; error?: string };
  presupuesto_latencia_ms: {
    transcripcion_visible: number;
    sugerencia_visible: number;
    contexto_previo: number;
  };
}

export interface Overview {
  llamadas_en_bandeja: number;
  clientes: number;
  transacciones: number;
  comercios: number;
  casos_abiertos: number;
  casos_por_vencer: number;
  documentos_kb: number;
  llamadas_atendidas: number;
}

export interface CustomerRow {
  customer_id: string;
  full_name: string;
  document_masked: string;
  segment: string;
  city: string | null;
  district: string | null;
  customer_since: string;
  productos: number;
  casos_abiertos: number;
  vulnerabilities: string[];
}

export interface ScenarioRow {
  scenario_id: string;
  customer_id: string;
  customer_name: string;
  expected_intent: string;
  narrative: string;
  expects_case: boolean;
  expected_case_type: string | null;
  focus_amount: string | null;
  focus_descriptor: string | null;
  focus_merchant: string | null;
  prior_purchases_90d: number | null;
  ordinal: number;
}

export const endpoints = {
  login: (username: string, password: string) =>
    api.post<LoginResponse>("/api/auth/login", { username, password }).then((r) => r.data),

  me: () => api.get<Agent>("/api/auth/me").then((r) => r.data),

  health: () => api.get<Health>("/health").then((r) => r.data),

  inbound: () => api.get<InboundCall[]>("/api/calls/inbound").then((r) => r.data),

  callContext: (callId: string) =>
    api.get<ContextResponse>(`/api/calls/${callId}/context`).then((r) => r.data),

  overview: () => api.get<Overview>("/api/stats/overview").then((r) => r.data),

  customers: (q: string) =>
    api.get<CustomerRow[]>("/api/customers", { params: { q, limit: 100 } }).then((r) => r.data),

  evaluationScenarios: () =>
    api.get<ScenarioRow[]>("/api/evaluation/scenarios").then((r) => r.data),
};

/**
 * Claves de caché de react-query.
 *
 * Centralizadas para que invalidar desde una mutación no dependa de repetir el
 * mismo array literal en dos archivos y acertar.
 */
export const queryKeys = {
  me: ["auth", "me"] as const,
  health: ["health"] as const,
  inbound: ["calls", "inbound"] as const,
  overview: ["stats", "overview"] as const,
  customers: (q: string) => ["customers", q] as const,
  evaluation: ["evaluation", "scenarios"] as const,
  callContext: (callId: string) => ["calls", callId, "context"] as const,
};
