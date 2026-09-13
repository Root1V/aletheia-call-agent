import type { TrustState } from "../lib/types";

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

interface Props {
  name: string;
  documentMasked: string;
  documentType: string;
  segment: string;
  customerSince: string;
  trust: TrustState;
  vulnerabilities: string[];
}

/**
 * Zona 0 del workspace.
 *
 * Va arriba de todo porque ninguna otra información es utilizable si no se
 * sabe con quién se está hablando, y porque ninguna acción sensible debe
 * ofrecerse por encima del nivel de verificación alcanzado.
 */
export function TrustBar(p: Props) {
  const anios = new Date().getFullYear() - new Date(p.customerSince).getFullYear();
  const nivelOk = p.trust.level === "verificado";
  const fraudeAlto = p.trust.fraud_risk_score >= 0.5;
  const vozSospechosa = (p.trust.synthetic_voice_score ?? 0) >= 0.5;

  return (
    <div className="trustbar">
      <div className="who">
        <span className="name">{p.name}</span>
        <span className="meta">
          {p.documentType} {p.documentMasked} · {p.segment} · cliente hace {anios} a
        </span>
      </div>

      <div className="spacer" />

      {p.vulnerabilities.length > 0 && (
        <span className="pill warn" title="Vulnerabilidad declarada por el cliente">
          Trato adaptado: {p.vulnerabilities.map((v) => v.replaceAll("_", " ")).join(", ")}
        </span>
      )}

      <span className={`pill ${nivelOk ? "ok" : "warn"}`}>
        {ETIQUETA_NIVEL[p.trust.level] ?? p.trust.level}
        {p.trust.factors.length > 0 && (
          <span style={{ fontWeight: 440, opacity: 0.85 }}>
            {" "}
            ({p.trust.factors.map((f) => ETIQUETA_FACTOR[f.kind] ?? f.kind).join(" + ")})
          </span>
        )}
      </span>

      <span className={`pill ${fraudeAlto ? "danger" : "mute"}`}>
        Riesgo de fraude {fraudeAlto ? "alto" : "bajo"}
      </span>

      {/*
        La voz se muestra como UNA señal más, nunca como el factor que
        autentica. El 91% de los bancos de EE.UU. está reconsiderando la
        biometría de voz por el riesgo de clonación con IA, y un panel que la
        presente como prueba de identidad enseña justo el hábito equivocado.
      */}
      {p.trust.synthetic_voice_score !== null && (
        <span
          className={`pill ${vozSospechosa ? "danger" : "mute"}`}
          title="Señal de riesgo, no un factor de autenticación"
        >
          Voz sintética: {vozSospechosa ? "posible" : "no detectada"}
        </span>
      )}

      {p.trust.step_up_required_for.length > 0 && (
        <span
          className="pill info"
          title={`Estas acciones exigen verificación adicional: ${p.trust.step_up_required_for.join(", ")}`}
        >
          Step-up para {p.trust.step_up_required_for.length} acciones
        </span>
      )}
    </div>
  );
}
