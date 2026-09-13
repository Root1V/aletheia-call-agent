import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    // Puerto propio y fijo: el 5173 por defecto ya lo usa otro proyecto en
    // esta máquina, y que Vite salte de puerto solo hace que la URL de la demo
    // cambie entre arranques.
    port: 5180,
    strictPort: true,
    proxy: {
      // El frontend habla siempre con su propio origen: así el WebSocket y la
      // API comparten sesión y no hace falta CORS ni configurar dos URLs.
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/health": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/ws": { target: "ws://127.0.0.1:8000", ws: true },
    },
  },
});
