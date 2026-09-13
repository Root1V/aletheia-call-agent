import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import { App } from "./App";
import { AuthProvider } from "./features/auth/AuthProvider";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // 30 s de frescura: el contexto de una llamada no cambia mientras el
      // ejecutivo lo mira, y refetchear en cada foco de ventana haría parpadear
      // el panel justo cuando está leyéndolo en voz alta.
      staleTime: 30_000,
      retry: (fallos, error) => {
        // Un 401 o un 403 no se arregla reintentando: el interceptor ya cerró
        // la sesión y reintentar sólo retrasa la redirección al login.
        const status = (error as { response?: { status?: number } })?.response?.status;
        if (status === 401 || status === 403) return false;
        return fallos < 2;
      },
      refetchOnWindowFocus: false,
    },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <App />
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
