import { createContext, use } from "react";

import type { Agent } from "@/lib/api/endpoints";

export interface AuthState {
  agent: Agent | null;
  /** Aún comprobando si el token guardado sigue siendo válido. */
  cargando: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

export const AuthContext = createContext<AuthState | null>(null);

export function useAuth(): AuthState {
  const ctx = use(AuthContext);
  if (!ctx) throw new Error("useAuth debe usarse dentro de <AuthProvider>");
  return ctx;
}
