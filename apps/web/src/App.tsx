import { Loader2 } from "lucide-react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";

import { useAuth } from "@/features/auth/auth-context";
import { CallWorkspacePage } from "@/pages/CallWorkspacePage";
import { CustomersPage } from "@/pages/CustomersPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { EvaluationPage } from "@/pages/EvaluationPage";
import { InboxPage } from "@/pages/InboxPage";
import { LoginPage } from "@/pages/LoginPage";
import { SettingsPage } from "@/pages/SettingsPage";

function Protegida({ children }: { children: React.ReactNode }) {
  const { agent, cargando } = useAuth();
  const location = useLocation();

  // Mientras se comprueba el token guardado no se puede decidir: redirigir al
  // login en este momento expulsaría en cada recarga a alguien que sí tiene
  // sesión válida.
  if (cargando) {
    return (
      <div className="grid min-h-screen place-items-center">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
        <span className="sr-only">Comprobando sesión</span>
      </div>
    );
  }

  if (!agent) {
    // Se recuerda a dónde iba para volver ahí después de entrar.
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return <>{children}</>;
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <Protegida>
            <DashboardPage />
          </Protegida>
        }
      />
      <Route
        path="/bandeja"
        element={
          <Protegida>
            <InboxPage />
          </Protegida>
        }
      />
      <Route
        path="/llamadas/:callId"
        element={
          <Protegida>
            <CallWorkspacePage />
          </Protegida>
        }
      />
      <Route
        path="/clientes"
        element={
          <Protegida>
            <CustomersPage />
          </Protegida>
        }
      />
      <Route
        path="/evaluacion"
        element={
          <Protegida>
            <EvaluationPage />
          </Protegida>
        }
      />
      <Route
        path="/ajustes"
        element={
          <Protegida>
            <SettingsPage />
          </Protegida>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
