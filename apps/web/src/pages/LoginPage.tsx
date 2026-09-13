import { AlertCircle, Eye, EyeOff, Loader2, LockKeyhole } from "lucide-react";
import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { BrandMark } from "@/components/BrandMark";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/features/auth/auth-context";
import { mensajeDeError } from "@/lib/api/client";

export function LoginPage() {
  const { agent, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [verClave, setVerClave] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  if (agent) {
    // Vuelve a donde iba antes de que la sesión lo interrumpiera, no siempre al
    // inicio: si el token expiró mientras miraba una llamada, devolverlo a la
    // bandeja le obliga a buscarla otra vez.
    const destino = (location.state as { from?: string } | null)?.from ?? "/";
    return <Navigate to={destino} replace />;
  }

  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setEnviando(true);
    try {
      await login(username.trim(), password);
      navigate((location.state as { from?: string } | null)?.from ?? "/", { replace: true });
    } catch (err) {
      setError(mensajeDeError(err, "No se pudo iniciar sesión"));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-[1.1fr_1fr]">
      {/* Panel de marca. Se oculta por debajo de lg: en pantalla pequeña el
          formulario es lo único que importa. */}
      <aside className="relative hidden overflow-hidden bg-gradient-to-br from-primary via-violet-600 to-indigo-700 p-12 text-white lg:flex lg:flex-col lg:justify-between">
        <div
          className="pointer-events-none absolute -right-24 -top-24 size-96 rounded-full bg-white/10 blur-3xl"
          aria-hidden
        />
        <div
          className="pointer-events-none absolute -bottom-32 -left-16 size-96 rounded-full bg-white/10 blur-3xl"
          aria-hidden
        />

        <div className="relative flex items-center gap-3">
          <BrandMark className="bg-white/15 backdrop-blur" size={44} />
          <div>
            <p className="text-lg font-semibold leading-tight">Copiloto de Atención</p>
            <p className="text-sm text-white/70">Banca · Perú</p>
          </div>
        </div>

        <div className="relative max-w-md space-y-6">
          <h1 className="text-3xl font-semibold leading-tight">
            El contexto de la llamada, antes de descolgar.
          </h1>
          <ul className="space-y-3 text-sm text-white/80">
            <li>Por qué llama el cliente, con la evidencia que lo respalda.</li>
            <li>El cargo en disputa traducido a un comercio real y reconocible.</li>
            <li>El plazo regulatorio de cada reclamo, a la vista.</li>
          </ul>
        </div>

        <p className="relative text-xs text-white/50">
          Plataforma interna. El acceso queda registrado en el log de auditoría.
        </p>
      </aside>

      <main className="flex items-center justify-center p-6 sm:p-12">
        <div className="w-full max-w-sm">
          <div className="mb-8 flex items-center gap-3 lg:hidden">
            <BrandMark size={40} />
            <p className="text-lg font-semibold">Copiloto de Atención</p>
          </div>

          <h2 className="text-2xl font-semibold tracking-tight">Iniciar sesión</h2>
          <p className="mt-1.5 text-sm text-muted-foreground">
            Usa las credenciales que te asignó tu administrador.
          </p>

          <form onSubmit={enviar} className="mt-8 space-y-4" noValidate>
            <div className="space-y-1.5">
              <Label htmlFor="username">Usuario</Label>
              <Input
                id="username"
                name="username"
                autoComplete="username"
                autoFocus
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                aria-invalid={error ? true : undefined}
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="password">Contraseña</Label>
              <div className="relative">
                <Input
                  id="password"
                  name="password"
                  type={verClave ? "text" : "password"}
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  aria-invalid={error ? true : undefined}
                  className="pr-10"
                />
                <button
                  type="button"
                  onClick={() => setVerClave((v) => !v)}
                  className="absolute inset-y-0 right-0 grid w-10 place-items-center text-muted-foreground transition-colors hover:text-foreground"
                  aria-label={verClave ? "Ocultar contraseña" : "Mostrar contraseña"}
                >
                  {verClave ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                </button>
              </div>
            </div>

            {error && (
              <p
                role="alert"
                className="flex items-start gap-2 rounded-md bg-danger-soft px-3 py-2 text-sm text-danger"
              >
                <AlertCircle className="mt-0.5 size-4 shrink-0" />
                {error}
              </p>
            )}

            <Button type="submit" size="lg" className="w-full" disabled={enviando}>
              {enviando ? (
                <>
                  <Loader2 className="animate-spin" />
                  Entrando…
                </>
              ) : (
                <>
                  <LockKeyhole />
                  Entrar
                </>
              )}
            </Button>
          </form>

          <p className="mt-6 flex items-start gap-2 text-xs leading-relaxed text-muted-foreground">
            No existe registro público: las altas las hace un administrador. Si no puedes entrar,
            escribe a soporte interno.
          </p>

          {/* Credenciales de la demo. `import.meta.env.DEV` las elimina del
              bundle de producción en tiempo de compilación, así que no hay
              riesgo de que un despliegue las publique. */}
          {import.meta.env.DEV && (
            <div className="mt-6 rounded-md border border-dashed border-border bg-muted/50 p-3 text-xs text-muted-foreground">
              <p className="font-medium text-foreground">Solo en desarrollo</p>
              <p className="mt-1 font-mono">carlos · demo-copiloto-2026</p>
              <p className="mt-1">
                Se crean con <span className="font-mono">scripts/create_admin.py</span>.
              </p>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
