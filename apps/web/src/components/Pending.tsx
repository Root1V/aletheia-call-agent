/**
 * Marcador de una zona del workspace todavía no construida.
 *
 * Se muestra explícitamente en lugar de dejar un hueco o, peor, de rellenarlo
 * con datos falsos que parezcan reales. En una demo para un comité, una
 * transcripción simulada indistinguible de una real es la forma más rápida de
 * perder la confianza cuando alguien pregunta de dónde salió.
 */
export function Pending({ title, phase, children }: {
  title: string;
  phase: string;
  children: React.ReactNode;
}) {
  return (
    <section className="card">
      <header>
        <h2>{title}</h2>
        <span className="pill mute">{phase}</span>
      </header>
      <div className="body">
        <p style={{ margin: 0, color: "var(--ink-2)", fontSize: 13, lineHeight: 1.55 }}>
          {children}
        </p>
      </div>
    </section>
  );
}
