import { useState, useEffect } from 'react';
import { fetchProfile, postProfileSynthesize } from '../../api';

const DOMAIN_LABELS: Record<string, string> = {
  identity: 'Identidad',
  patterns: 'Patrones',
  sabotage: 'Autosabotaje',
  strengths: 'Fortalezas',
  relationships: 'Relaciones',
  narrative: 'Narrativa',
  goals: 'Metas',
};

const FACT_TYPE_LABELS: Record<string, string> = {
  declared: 'Declarado por ti',
  behavioral: 'Observado (conducta)',
  inferred: 'Inferido',
  contradicted: 'En tensión / contradicción',
};

const CONFIDENCE_LABELS: Record<string, string> = {
  emerging: 'Emergente',
  developing: 'En desarrollo',
  established: 'Establecido',
};

function formatWhen(ts: string): string {
  const d = new Date(ts + 'Z');
  return d.toLocaleDateString('es-MX', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

interface SummaryRow {
  domain: string;
  summary_text: string;
  last_updated: string;
}

interface FactRow {
  id: number;
  domain: string;
  statement: string;
  fact_type: string;
  confidence: string;
  weight: number;
  source_type: string | null;
}

interface MemoryRow {
  id: number;
  timestamp: string;
  topic: string;
  raw_transcript: string;
  life_period: string;
}

export function PerfilConocimiento() {
  const [summaries, setSummaries] = useState<SummaryRow[]>([]);
  const [facts, setFacts] = useState<FactRow[]>([]);
  const [memories, setMemories] = useState<MemoryRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [synthBusy, setSynthBusy] = useState(false);
  const [synthMessage, setSynthMessage] = useState<string | null>(null);

  const refresh = () => {
    setLoading(true);
    setSynthMessage(null);
    fetchProfile()
      .then(
        (data: {
          summaries: SummaryRow[];
          facts: FactRow[];
          memories?: MemoryRow[];
        }) => {
          setSummaries(data.summaries || []);
          setFacts(data.facts || []);
          setMemories(data.memories || []);
        },
      )
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    refresh();
  }, []);

  const runSynthesize = async () => {
    setSynthBusy(true);
    setSynthMessage(null);
    try {
      const res = await postProfileSynthesize();
      setSynthMessage((res as { message?: string }).message || 'Listo.');
      await refresh();
    } catch {
      setSynthMessage('No se pudo regenerar (¿Ollama encendido?).');
    } finally {
      setSynthBusy(false);
    }
  };

  const hasFacts = facts.length > 0;
  const hasMemories = memories.length > 0;
  const domainFilled = summaries.some((s) => (s.summary_text || '').trim());

  return (
    <div className="max-w-3xl mx-auto px-4 py-6 space-y-8">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">Lo que Nash sabe de ti</h2>
          <p className="text-sm text-[var(--nash-text-muted)] mt-1">
            Todo local. Las secciones se actualizan en momentos distintos (ver recuadro).
          </p>
        </div>
        <div className="flex flex-wrap gap-2 shrink-0">
          <button
            type="button"
            onClick={refresh}
            className="text-xs text-[var(--nash-accent)] hover:underline cursor-pointer px-2 py-1"
          >
            Actualizar vista
          </button>
          <button
            type="button"
            disabled={synthBusy}
            onClick={runSynthesize}
            className="text-xs bg-[var(--nash-accent)]/20 border border-[var(--nash-accent)]/40 text-[var(--nash-accent)] rounded-lg px-3 py-1.5 hover:bg-[var(--nash-accent)]/30 disabled:opacity-40 cursor-pointer disabled:cursor-not-allowed"
          >
            {synthBusy ? 'Regenerando...' : 'Regenerar resumenes por dominio'}
          </button>
        </div>
      </div>

      <div className="bg-[var(--nash-surface-2)] border border-[var(--nash-border)] rounded-xl p-4 text-sm text-[var(--nash-text-muted)] leading-relaxed space-y-2">
        <p className="text-[var(--nash-text)] font-medium text-xs uppercase tracking-wide">
          ¿Cuándo se actualiza cada parte?
        </p>
        <ul className="list-disc pl-5 space-y-1">
          <li>
            <span className="text-[var(--nash-text)] font-medium">Hechos</span> — cuando Nash usa la herramienta{' '}
            <code className="text-xs bg-[var(--nash-bg)] px-1 rounded">log_profile_fact</code> en la conversación.
          </li>
          <li>
            <span className="text-[var(--nash-text)] font-medium">Memorias</span> — cuando usa{' '}
            <code className="text-xs bg-[var(--nash-bg)] px-1 rounded">log_memory</code>.
          </li>
          <li>
            <span className="text-[var(--nash-text)] font-medium">Resúmenes por dominio</span> — no se rellenan solos
            todavía: pulsa Regenerar resúmenes por dominio para que el modelo local lea tus últimas entradas y escriba
            un párrafo corto por dominio. Más adelante: síntesis automática en segundo plano (plan fase 2).
          </li>
        </ul>
      </div>

      {synthMessage && (
        <p className="text-sm text-[var(--nash-text-muted)]">{synthMessage}</p>
      )}

      {loading && <p className="text-sm text-[var(--nash-text-muted)]">Cargando…</p>}

      {!loading && summaries.length > 0 && (
        <section>
          <h3 className="text-sm font-medium text-[var(--nash-text)] mb-3">Resúmenes por dominio</h3>
          {!domainFilled && (
            <p className="text-xs text-[var(--nash-warning)] mb-2">
              Los dominios estan vacios hasta que pulses "Regenerar resumenes por dominio".
            </p>
          )}
          <div className="space-y-2">
            {summaries.map((s) => {
              const text = (s.summary_text || '').trim();
              return (
                <div
                  key={s.domain}
                  className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded-lg p-4"
                >
                  <p className="text-xs text-[var(--nash-accent)] uppercase tracking-wide mb-1">
                    {DOMAIN_LABELS[s.domain] || s.domain}
                  </p>
                  <p className="text-sm text-[var(--nash-text)] leading-relaxed">
                    {text || <span className="text-[var(--nash-text-muted)]">Sin resumen aún.</span>}
                  </p>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {!loading && hasFacts && (
        <section>
          <h3 className="text-sm font-medium text-[var(--nash-text)] mb-3">
            Hechos sobre ti ({facts.length})
          </h3>
          <ul className="space-y-2">
            {facts.map((f) => (
              <li
                key={f.id}
                className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded-lg p-3 text-sm"
              >
                <span className="text-xs text-[var(--nash-text-muted)]">
                  {DOMAIN_LABELS[f.domain] || f.domain} · {FACT_TYPE_LABELS[f.fact_type] || f.fact_type} ·{' '}
                  {CONFIDENCE_LABELS[f.confidence] || f.confidence}
                  {f.source_type ? ` · origen: ${f.source_type}` : ''}
                </span>
                <p className="text-[var(--nash-text)] mt-1 leading-relaxed">{f.statement}</p>
              </li>
            ))}
          </ul>
        </section>
      )}

      {!loading && hasMemories && (
        <section>
          <h3 className="text-sm font-medium text-[var(--nash-text)] mb-3">
            Memorias guardadas ({memories.length})
          </h3>
          <div className="space-y-2">
            {memories.map((m) => (
              <div
                key={m.id}
                className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded-lg p-3"
              >
                <p className="text-xs text-[var(--nash-accent)]">{m.topic}</p>
                <p className="text-xs text-[var(--nash-text-muted)] mt-0.5">
                  {formatWhen(m.timestamp)} · {m.life_period}
                </p>
                <p className="text-sm text-[var(--nash-text-muted)] mt-2 line-clamp-4 leading-relaxed">
                  {m.raw_transcript}
                </p>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
