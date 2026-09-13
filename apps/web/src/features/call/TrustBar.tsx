import { ShieldAlert, ShieldCheck, ShieldQuestion } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { Customer, TrustState } from "@/lib/types";

const ETIQUETA_NIVEL: Record<string, string> = {
  verificado: "Verificado",
  parcial: "Verificación parcial",
  no_verificado: "Sin verificar",
  fallido: "Verificación fallida",
};

const ETIQUETA_FACTOR: Record<string, string> = {
  ani_match: "número registrado",
  pregunta_seguridad: "pregunta de seguridad",
  otp: "clave temporal",
  voz: "voz",
  app_push: "confirmación en la app",
};

/**
 * Zona 0: identidad y confianza.
 *
 * Va arriba de todo porque ninguna otra información es utilizable sin saber
 * con quién se habla, y porque ninguna acción sensible debe ofrecerse por
 * encima del nivel de verificación alcanzado.
 */
export function TrustBar({ customer, trust }: { customer: Customer; trust: TrustState }) {
  const anios = new Date().getFullYear() - new Date(customer.customer_since).getFullYear();
  const verificado = trust.level === "verificado";
  const fraudeAlto = trust.fraud_risk_score >= 0.5;
  const vozSospechosa = (trust.synthetic_voice_score ?? 0) >= 0.5;

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg border border-border bg-card px-4 py-3">
      <div className="flex min-w-0 items-baseline gap-2.5">
        <span className="truncate text-base font-semibold">{customer.full_name}</span>
        <span className="truncate text-[0.8rem] text-muted-foreground">
          {customer.document_type} {customer.document_masked} · {customer.segment} · cliente hace{" "}
          {anios} a
        </span>
      </div>

      <div className="flex flex-1 flex-wrap items-center justify-end gap-2">
        {customer.vulnerabilities.length > 0 && (
          <Badge
            variant="warning"
            title="Vulnerabilidad declarada por el cliente. Sólo para adaptar el trato, nunca para precios ni ofertas."
          >
            Trato adaptado: {customer.vulnerabilities.map((v) => v.replaceAll("_", " ")).join(", ")}
          </Badge>
        )}

        <Badge variant={verificado ? "success" : "warning"}>
          {verificado ? <ShieldCheck className="size-3" /> : <ShieldQuestion className="size-3" />}
          {ETIQUETA_NIVEL[trust.level] ?? trust.level}
          {trust.factors.length > 0 && (
            <span className="font-normal opacity-80">
              ({trust.factors.map((f) => ETIQUETA_FACTOR[f.kind] ?? f.kind).join(" + ")})
            </span>
          )}
        </Badge>

        <Badge variant={fraudeAlto ? "danger" : "muted"}>
          {fraudeAlto && <ShieldAlert className="size-3" />}
          Riesgo de fraude {fraudeAlto ? "alto" : "bajo"}
        </Badge>

        {/*
          La voz aparece como UNA señal más, nunca como el factor que autentica.
          El 91% de los bancos de EE.UU. está reconsiderando la biometría de voz
          por el riesgo de clonación con IA, y un panel que la presente como
          prueba de identidad enseña justo el hábito equivocado.
        */}
        {trust.synthetic_voice_score !== null && (
          <Badge
            variant={vozSospechosa ? "danger" : "muted"}
            title="Señal de riesgo, no un factor de autenticación"
          >
            Voz sintética: {vozSospechosa ? "posible" : "no detectada"}
          </Badge>
        )}

        {trust.step_up_required_for.length > 0 && (
          <Badge title={`Exigen verificación adicional: ${trust.step_up_required_for.join(", ")}`}>
            Step-up para {trust.step_up_required_for.length} acciones
          </Badge>
        )}
      </div>
    </div>
  );
}
