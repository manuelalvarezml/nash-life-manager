interface StreamResponseProps {
  transcript: string;
  response: string;
  toolCalls: Array<{ name: string; args?: Record<string, unknown>; result?: string }>;
  isProcessing: boolean;
}

export function StreamResponse({ transcript, response, toolCalls, isProcessing }: StreamResponseProps) {
  if (!transcript && !response && !isProcessing) return null;

  return (
    <div className="w-full max-w-xl space-y-5">
      {transcript && (
        <div className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded-xl p-5">
          <p className="text-sm text-[var(--nash-text-muted)] mb-2 uppercase tracking-wide font-medium">Tu mensaje</p>
          <p className="text-base text-[var(--nash-text)] leading-relaxed">{transcript}</p>
        </div>
      )}

      {response && (
        <div className="bg-[var(--nash-prussian-soft)] border border-[var(--nash-prussian)]/30 rounded-xl p-5">
          <p className="text-sm text-[var(--nash-prussian)] mb-2 uppercase tracking-wide font-medium">Nash</p>
          <p className="text-base text-[var(--nash-text)] leading-relaxed whitespace-pre-wrap">{response}</p>
        </div>
      )}

      {toolCalls.length > 0 && (
        <div className="bg-[var(--nash-surface-2)] border border-[var(--nash-border)] rounded-xl p-4">
          <p className="text-sm text-[var(--nash-text-muted)] mb-3 uppercase tracking-wide font-medium">Acciones realizadas</p>
          <div className="space-y-2">
            {toolCalls.map((tc, i) => (
              <div key={i} className="text-sm font-mono text-[var(--nash-text-muted)]">
                <span className="text-[var(--nash-teal)]">-</span>{' '}
                {tc.name}
                {tc.result && <span className="text-[var(--nash-text-muted)]"> - {tc.result}</span>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
