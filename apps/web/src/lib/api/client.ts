import axios, { AxiosError } from "axios";

/**
 * Cliente HTTP con el token adjunto y el 401 manejado en un solo sitio.
 *
 * Sobre dónde vive el token: en `localStorage`. Es el patrón habitual para un
 * SPA con bearer tokens, pero conviene tener claro el intercambio — una cookie
 * `httpOnly` sería inmune a que un XSS lea el token, a cambio de manejar CSRF
 * y `SameSite`. Con un token de 9 horas y una herramienta interna, el riesgo
 * real está en el XSS mismo; si el banco exige cookies httpOnly, el cambio
 * queda contenido en este archivo.
 */

const CLAVE_TOKEN = "cea.token";

export const tokenStore = {
  get: () => localStorage.getItem(CLAVE_TOKEN),
  set: (token: string) => localStorage.setItem(CLAVE_TOKEN, token),
  clear: () => localStorage.removeItem(CLAVE_TOKEN),
};

export const api = axios.create({
  baseURL: "/",
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config) => {
  const token = tokenStore.get();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

/** Suscriptores al evento de sesión caída, para que el router redirija. */
const alPerderSesion = new Set<() => void>();

export function onSessionLost(cb: () => void): () => void {
  alPerderSesion.add(cb);
  return () => alPerderSesion.delete(cb);
}

api.interceptors.response.use(
  (res) => res,
  (error: AxiosError) => {
    // El 401 se maneja una sola vez aquí y no en cada pantalla: si cada
    // componente decidiera por su cuenta qué hacer con una sesión expirada,
    // terminaríamos con tres comportamientos distintos y alguno dejaría al
    // ejecutivo mirando una pantalla vacía sin explicación.
    //
    // El propio login se excluye: ahí un 401 significa "credenciales
    // incorrectas", no "sesión expirada", y cerrar sesión en ese momento
    // borraría el formulario que el usuario está usando.
    const esLogin = error.config?.url?.includes("/api/auth/login");
    if (error.response?.status === 401 && !esLogin) {
      tokenStore.clear();
      alPerderSesion.forEach((cb) => cb());
    }
    return Promise.reject(error);
  },
);

/** Mensaje presentable a partir de un error de axios. */
export function mensajeDeError(error: unknown, porDefecto = "Ocurrió un error"): string {
  if (axios.isAxiosError(error)) {
    const detail = (error.response?.data as { detail?: string } | undefined)?.detail;
    if (detail) return detail;
    if (error.code === "ERR_NETWORK") {
      return "No se pudo conectar con el servidor. ¿Está la API levantada?";
    }
  }
  return porDefecto;
}
