import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, PhoneOff } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { AppShell } from "@/components/layout/AppShell";
import { Cargando, ErrorDeCarga } from "@/components/StateMessage";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { buttonVariants } from "@/components/ui/button-variants";
import { Card } from "@/components/ui/card";
import { Full360 } from "@/features/call/Full360";
import { LiveTranscript } from "@/features/call/LiveTranscript";
import { PendingPanel } from "@/features/call/PendingPanel";
import { TransactionEvidence } from "@/features/call/TransactionEvidence";
import { TrustBar } from "@/features/call/TrustBar";
import { useCallStream } from "@/features/call/useCallStream";
import { WhyCalling } from "@/features/call/WhyCalling";
import { mensajeDeError } from "@/lib/api/client";
import { endpoints, queryKeys } from "@/lib/api/endpoints";

export function CallWorkspacePage() {
  const { callId = "" } = useParams();
  const navigate = useNavigate();

  const { turnos, estado: estadoStream } = useCallStream(callId);

  const contexto = useQuery({
    queryKey: queryKeys.callContext(callId),
    queryFn: () => endpoints.callContext(callId),
    enabled: Boolean(callId),
  });

  if (contexto.isPending) {
    return (
      <AppShell titulo="Llamada" subtitulo="Armando el contexto…">
        <Cargando texto="Recuperando el contexto de la llamada…" />
      </AppShell>
    );
  }

  if (contexto.isError) {
    return (
      <AppShell titulo="Llamada">
        <Card className="max-w-xl">
          <ErrorDeCarga
            mensaje={mensajeDeError(contexto.error)}
            onReintentar={() => contexto.refetch()}
          />
          <div className="flex justify-center pb-6">
            <Link to="/bandeja" className={buttonVariants({ variant: "outline", size: "sm" })}>
              <ArrowLeft />
              Volver a la bandeja
            </Link>
          </div>
        </Card>
      </AppShell>
    );
  }

  const { context: c, build_ms } = contexto.data;

  return (
    <AppShell
      titulo="Llamada en curso"
      subtitulo={c.call_id.replace("call-", "").replaceAll("_", " ")}
      acciones={
        <div className="flex items-center gap-2">
          {/* El tiempo de armado del pre-pop, a la vista y no sólo en las
              métricas: el presupuesto de latencia es el requisito no funcional
              número uno y debe poder comprobarse sin abrir Grafana. */}
          <Badge
            variant="muted"
            className="tabular font-mono"
            title="Tiempo de armado del contexto previo a descolgar"
          >
            pre-pop {build_ms} ms
          </Badge>
          <Button variant="outline" size="sm" onClick={() => navigate("/bandeja")}>
            <PhoneOff />
            Colgar
          </Button>
        </div>
      }
    >
      <div className="space-y-3">
        <TrustBar customer={c.customer} trust={c.trust} />

        {/*
          Las tres columnas sólo aparecen a partir de 2xl.
          
          En una pantalla de 1440 px, tres columnas dejan unos 390 px cada una y
          las líneas de los movimientos —fecha, categoría, canal, dispositivo—
          se parten en tres renglones. Un panel denso que se lee de un vistazo
          deja de leerse de un vistazo. Entre xl y 2xl van dos columnas, con la
          conversación y el copiloto apilados a la derecha.
        */}
        <div className="grid items-start gap-3 xl:grid-cols-[minmax(420px,1fr)_minmax(360px,0.9fr)] 2xl:grid-cols-[minmax(420px,1fr)_minmax(400px,1.15fr)_minmax(320px,0.95fr)]">
          <div className="space-y-3">
            <WhyCalling
              intent={c.intent}
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

          <div className="space-y-3 2xl:contents">
            <div className="space-y-3">
            <LiveTranscript turnos={turnos} estado={estadoStream} />
            <PendingPanel titulo="Emoción del cliente" fase="Fase 3">
              Barras en vivo de frustración, satisfacción, confusión y urgencia, calculadas sólo
              sobre el audio del cliente. Fusiona señal acústica, textual y conversacional, con
              calibración y banda de incertidumbre.
            </PendingPanel>
            </div>

            <div className="space-y-3">
            <PendingPanel titulo="Copiloto" fase="Fase 4">
              Respuesta sugerida adaptada al estado emocional, con cita obligatoria al conocimiento
              del banco y verificación de toda cifra contra el tarifario estructurado.
            </PendingPanel>
            <PendingPanel titulo="Clasificación del caso" fase="Fase 5">
              Propuesta de reclamo o requerimiento bajo la Ley 31763, con su justificación y la
              evidencia de la conversación, para que el ejecutivo confirme o corrija.
            </PendingPanel>
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
