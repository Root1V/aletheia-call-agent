import { useCallback, useEffect, useState } from "react";

type Tema = "light" | "dark" | "system";

const CLAVE = "cea.tema";

function aplicar(tema: Tema) {
  const oscuro =
    tema === "dark" ||
    (tema === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.classList.toggle("dark", oscuro);
}

/**
 * Tema del portal.
 *
 * "system" es el valor por defecto: un ejecutivo que trabaja de noche en un
 * piso con poca luz ya configuró esa preferencia en su sistema, y volver a
 * preguntársela en cada aplicación es ruido.
 */
export function useTheme() {
  const [tema, setTemaEstado] = useState<Tema>(
    () => (localStorage.getItem(CLAVE) as Tema | null) ?? "system",
  );

  useEffect(() => {
    aplicar(tema);
    if (tema !== "system") return;
    // Si sigue al sistema, hay que reaccionar cuando el sistema cambie: macOS
    // alterna claro/oscuro al atardecer y la pestaña puede llevar horas
    // abierta.
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => aplicar("system");
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [tema]);

  const setTema = useCallback((nuevo: Tema) => {
    localStorage.setItem(CLAVE, nuevo);
    setTemaEstado(nuevo);
  }, []);

  return { tema, setTema };
}

export type { Tema };
