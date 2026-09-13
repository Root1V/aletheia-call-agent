import { useCallback, useEffect, useState } from "react";

import { Full360 } from "./components/Full360";
import { Pending } from "./components/Pending";
import { TransactionEvidence } from "./components/TransactionEvidence";
import { TrustBar } from "./components/TrustBar";
import { WhyCalling } from "./components/WhyCalling";
import { api } from "./lib/api";
import type { ContextResponse, InboundCall } from "./lib/types";

export function App() {
  const [calls, setCalls] = useState<InboundCall[] | null>(null);
  const [active, setActive] = useState<ContextResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.inbound().then(setCalls).catch((e: Error) => setError(e.message));
  }, []);

  const answer = useCallback(async (callId: string) => {
    setError(null);
    try {
      setActive(await api.context(callId));
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  if (error) {
    return (
      <div className="tray">
        <h1>No se pudo cargar</h1>
        <p className="lead">{error}</p>
        <p className="lead">
          Verificar que la infraestructura esté levantada y la base sembrada:
          <code> make up &amp;&amp; make seed &amp;&amp; make api</code>
        </p>
      </div>
    );
  }

  if (!active) {
    return <Tray calls={calls} onAnswer={answer} />;
  }

  const { context: c, build_ms } = active;

  return (
    <div className="app">
      <div className="topbar">
        <span className="brand">Copiloto de Atención</span>
        <span className="pill mute">{c.call_id.replace("call-", "")}</span>
        <div className="spacer" />
        <span className="buildms" title="Tiempo de armado del contexto previo a descolgar">
          pre-pop {build_ms} ms
        </span>
        <button className="btn" onClick={() => setActive(null)}>
          Colgar
        </button>
      </div>

      <TrustBar
        name={c.customer.full_name}
        documentMasked={c.customer.document_masked}
        documentType={c.customer.document_type}
        segment={c.customer.segment}
        customerSince={c.customer.customer_since}
        trust={c.trust}
        vulnerabilities={c.customer.vulnerabilities}
      />

      <div className="workspace">
        <div className="col">
          <WhyCalling
            intent={c.intent}
            events={c.recent_account_events}
            journey={c.digital_journey}
            cases={c.open_cases}
          />
          <TransactionEvidence
            transactions={c.relevant_transactions}
            focusId={c.focus_transaction_id}
            supportingIds={c.supporting_transaction_ids}
            attemptIds={c.related_attempt_ids}
          />
          <Full360 customer={c.customer} />
        </div>

        <div className="col">
          <Pending title="Conversación en vivo" phase="Fase 1">
            Aquí van la transcripción bilateral con separación por hablante y los parciales que se
            consolidan al cerrar cada turno. Requiere el agente de LiveKit y el servicio de ASR en
            streaming, que es la fase siguiente.
          </Pending>
          <Pending title="Emoción del cliente" phase="Fase 3">
            Barras en vivo de frustración, satisfacción, confusión y urgencia, calculadas sólo sobre
            el audio del cliente. Fusiona señal acústica, textual y conversacional, con calibración
            y banda de incertidumbre.
          </Pending>
        </div>

        <div className="col">
          <Pending title="Copiloto" phase="Fase 4">
            Respuesta sugerida adaptada al estado emocional, con cita obligatoria al conocimiento
            del banco y verificación de toda cifra contra el tarifario estructurado.
          </Pending>
          <Pending title="Clasificación del caso" phase="Fase 5">
            Propuesta de reclamo o requerimiento bajo la Ley 31763, con su justificación y la
            evidencia de la conversación, para que el ejecutivo confirme o corrija.
          </Pending>
        </div>
      </div>
    </div>
  );
}

function Tray({
  calls,
  onAnswer,
}: {
  calls: InboundCall[] | null;
  onAnswer: (callId: string) => void;
}) {
  return (
    <div className="tray">
      <h1>Llamadas entrantes</h1>
      <p className="lead">
        Escenarios guionados y reproducibles. Los mismos datos alimentan la demo y el conjunto de
        evaluación, así que lo que se ve aquí es exactamente lo que se mide.
      </p>

      {calls === null ? (
        <p className="empty">Cargando…</p>
      ) : calls.length === 0 ? (
        <p className="empty">
          Sin escenarios. Ejecutar <code>make seed</code>.
        </p>
      ) : (
        <div className="calls">
          {calls.map((c) => (
            <button key={c.call_id} className="call" onClick={() => onAnswer(c.call_id)}>
              <span className="top">
                <span className="cname">{c.customer_name}</span>
                <span className="pill mute">{c.segment}</span>
                <span className="pill info">{c.scenario_id.replaceAll("_", " ")}</span>
              </span>
              <span className="narr">{c.narrative}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
