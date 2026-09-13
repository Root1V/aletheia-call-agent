import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useState } from "react";

import { onSessionLost, tokenStore } from "@/lib/api/client";
import { endpoints, type Agent } from "@/lib/api/endpoints";

import { AuthContext } from "./auth-context";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [agent, setAgent] = useState<Agent | null>(null);
  // El estado inicial se DERIVA de si hay token, en vez de empezar siempre en
  // "cargando" y apagarlo desde el efecto. Poner setState en el cuerpo de un
  // efecto provoca un render en cascada en cada montaje de quien no tiene
  // sesión, que es justo el caso más frecuente en la pantalla de login.
  const [cargando, setCargando] = useState(() => Boolean(tokenStore.get()));
  const queryClient = useQueryClient();

  const logout = useCallback(() => {
    tokenStore.clear();
    setAgent(null);
    // La caché se vacía al cerrar sesión. Sin esto, el siguiente usuario que
    // entre en la misma pestaña vería por un instante los datos del anterior
    // —nombre de cliente, movimientos, reclamos— antes del primer refetch.
    queryClient.clear();
  }, [queryClient]);

  // Un token guardado sólo es una promesa: puede haber expirado o haber sido
  // emitido con un secreto ya rotado. Se comprueba contra el servidor antes de
  // dar la sesión por buena.
  useEffect(() => {
    if (!tokenStore.get()) return;
    let vigente = true;
    endpoints
      .me()
      .then((a) => vigente && setAgent(a))
      .catch(() => tokenStore.clear())
      .finally(() => vigente && setCargando(false));
    return () => {
      vigente = false;
    };
  }, []);

  useEffect(() => onSessionLost(() => setAgent(null)), []);

  const login = useCallback(async (username: string, password: string) => {
    const res = await endpoints.login(username, password);
    tokenStore.set(res.access_token);
    setAgent(res.agent);
  }, []);

  const value = useMemo(
    () => ({ agent, cargando, login, logout }),
    [agent, cargando, login, logout],
  );

  return <AuthContext value={value}>{children}</AuthContext>;
}
