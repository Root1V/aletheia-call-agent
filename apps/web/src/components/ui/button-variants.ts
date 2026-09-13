import { cva } from "class-variance-authority";

/**
 * Variantes del botón, en su propio módulo.
 *
 * Viven separadas del componente para que el archivo de `Button` exporte sólo
 * componentes: mezclar ambos rompe el refresco en caliente de Vite, que
 * recarga el módulo entero en lugar de aplicar el cambio en sitio.
 */
export const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-50 [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary/90",
        outline: "border border-input bg-card hover:bg-muted hover:text-foreground",
        ghost: "hover:bg-muted hover:text-foreground",
        subtle: "bg-muted text-foreground hover:bg-muted/70",
        danger: "bg-danger text-white hover:bg-danger/90",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        sm: "h-8 px-3",
        default: "h-9 px-4",
        lg: "h-11 px-6 text-[0.95rem]",
        icon: "size-9",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);
