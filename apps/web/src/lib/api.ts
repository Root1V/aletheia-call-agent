import type { ContextResponse, InboundCall } from "./types";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(path, { headers: { Accept: "application/json" } });
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText} en ${path}`);
  }
  return (await res.json()) as T;
}

export const api = {
  inbound: () => get<InboundCall[]>("/api/calls/inbound"),
  context: (callId: string) => get<ContextResponse>(`/api/calls/${callId}/context`),
};
