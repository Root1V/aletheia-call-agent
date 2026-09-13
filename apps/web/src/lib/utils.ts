import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Compone clases condicionales resolviendo colisiones de Tailwind.
 *
 * `clsx` arma la lista y `twMerge` deja la última de cada grupo en conflicto:
 * sin él, `cn("px-2", "px-4")` emite ambas y gana la que esté antes en el CSS
 * generado, no la que el autor escribió al final.
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
