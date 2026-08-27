import { useState, useEffect } from 'react';
import { fetchDebugLast } from '../../api';

interface DebugData {
  counts: {
    entries: number;
    memories: number;
    facts: number;
    semantic_units: number;
  };
  last_entry: {
    id: number;
    timestamp: string;
    entry_type: string;
    raw_transcript: string;
    summary: string;
    energy_level: number | null;
    audio_path: string | null;
  } | null;
  recent_facts: Array<{
    id: number;
    domain: string;
    statement: string;
    fact_type: string;
    confidence: string;
    created_at: string;
  }>;
  last_synthesis_at: string | null;
  implementation_status: Record<string, boolean>;
}

const FEATURE_LABELS: Record<string, string> = {
  audio_transcription: 'Transcripción de audio (MLX-Whisper)',
  diary_entries: 'Entradas de diario',
  profile_facts: 'Hechos del perfil',
  memories: 'Memorias',
  semantic_decomposition: 'Descomposición semántica',
  chroma_ingestion: 'Ingesta a ChromaDB',
  semantic_retrieval: 'Recuperación semántica en contexto',
  profile_synthesis_manual: 'Síntesis de perfil (manual)',
  profile_synthesis_auto: 'Síntesis de perfil (automática)',
  question_engine: 'Motor de preguntas diarias',
  self_profile_facts: 'Perfil biográfico (Sobre Mi)',
  work_module: 'Módulo de trabajo',
  goals_calendar: 'Metas y calendario',
  body_module: 'Módulo cuerpo (nutrición/ejercicio)',
  finance_module: 'Módulo finanzas',
};

const CONFIDENCE_STYLES: Record<string, { icon: string; color: string }> = {
  emerging: { icon: '~', color: 'text-[var(--nash-text-muted)]' },
  developing: { icon: '?', color: 'text-[var(--nash-warning)]' },
  established: { icon: '✓', color: 'text-[var(--nash-success)]' },
};

const FACT_TYPE_STYLES: Record<string, string> = {
  declared: 'bg-blue-500/20 text-blue-400',
  behavioral: 'bg-green-500/20 text-green-400',
  inferred: 'bg-purple-500/20 text-purple-400',
  contradicted: 'bg-red-500/20 text-red-400',
};

function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) return 'ahora';
  if (diffMins < 60) return `hace ${diffMins}m`;
  if (diffHours < 24) return `hace ${diffHours}h`;
  return `hace ${diffDays}d`;
}

export function Dev() {
  const [debug, setDebug] = useState<DebugData | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = async () => {
    setLoading(true);
    try {
      const debugData = await fetchDebugLast();
      setDebug(debugData);
    } catch (e) {
      console.error('Error loading debug data:', e);
    }
    setLoading(false);
  };

  useEffect(() => {
    const initialRefresh = window.setTimeout(() => void refresh(), 0);
    return () => window.clearTimeout(initialRefresh);
  }, []);

  const implementedCount = debug?.implementation_status
    ? Object.values(debug.implementation_status).filter(Boolean).length
    : 0;
  const totalFeatures = debug?.implementation_status
    ? Object.keys(debug.implementation_status).length
    : 0;

  return (
    <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-3 h-3 rounded-full bg-[var(--nash-success)] animate-pulse" />
          <h2 className="text-xl font-semibold">Panel de Desarrollo</h2>
        </div>
        <button
          onClick={refresh}
          disabled={loading}
          className="text-sm text-[var(--nash-accent)] hover:text-[var(--nash-accent)]/80
                     disabled:opacity-50 transition-colors flex items-center gap-1"
        >
          {loading ? (
            <span className="inline-block w-3 h-3 border border-current border-t-transparent rounded-full animate-spin" />
          ) : (
            '↻'
          )}
          <span>Actualizar</span>
        </button>
      </div>

      {/* Stats Grid */}
      {debug && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <StatCard label="Entradas" value={debug.counts.entries} />
          <StatCard label="Memorias" value={debug.counts.memories} />
          <StatCard label="Hechos" value={debug.counts.facts} />
          <StatCard label="Unidades Semánticas" value={debug.counts.semantic_units} />
        </div>
      )}

      {/* Implementation Status */}
      {debug?.implementation_status && (
        <div className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded-lg p-4">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-medium">Estado de Implementación</h3>
            <span className="text-xs text-[var(--nash-text-muted)]">
              {implementedCount}/{totalFeatures} completado
            </span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {Object.entries(debug.implementation_status).map(([feature, done]) => (
              <div
                key={feature}
                className={`flex items-center gap-2 text-sm py-1 ${
                  done ? 'text-[var(--nash-text)]' : 'text-[var(--nash-text-muted)]'
                }`}
              >
                <span className={done ? 'text-[var(--nash-success)]' : 'text-[var(--nash-text-muted)]'}>
                  {done ? '✓' : '○'}
                </span>
                <span>{FEATURE_LABELS[feature] || feature}</span>
              </div>
            ))}
          </div>
          {/* Progress bar */}
          <div className="mt-4 h-1.5 bg-[var(--nash-surface-2)] rounded-full overflow-hidden">
            <div
              className="h-full bg-[var(--nash-success)] transition-all duration-500"
              style={{ width: `${(implementedCount / totalFeatures) * 100}%` }}
            />
          </div>
        </div>
      )}

      {/* System Info */}
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded-lg p-3">
          <p className="text-xs text-[var(--nash-text-muted)] mb-1">Última síntesis</p>
          <p className="text-sm">
            {debug?.last_synthesis_at ? (
              <>
                <span className="text-[var(--nash-success)]">●</span>{' '}
                {formatRelativeTime(debug.last_synthesis_at)}
              </>
            ) : (
              <span className="text-[var(--nash-text-muted)]">Nunca</span>
            )}
          </p>
        </div>
        <div className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded-lg p-3">
          <p className="text-xs text-[var(--nash-text-muted)] mb-1">Modelo LLM</p>
          <p className="text-sm">
            <span className="text-[var(--nash-accent)]">drivedenpadev/deepseek-v3.2</span>
          </p>
        </div>
      </div>

      {/* Recent Facts (Color-coded) */}
      {debug && debug.recent_facts.length > 0 && (
        <div className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded-lg p-4">
          <h3 className="text-sm font-medium mb-3">Hechos Recientes</h3>
          <div className="space-y-2">
            {debug.recent_facts.map((fact) => {
              const conf = CONFIDENCE_STYLES[fact.confidence] || CONFIDENCE_STYLES.emerging;
              const typeStyle = FACT_TYPE_STYLES[fact.fact_type] || 'bg-gray-500/20 text-gray-400';
              return (
                <div key={fact.id} className="flex items-start gap-2 text-sm">
                  <span className={`${conf.color} text-lg leading-none mt-0.5`}>{conf.icon}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-0.5">
                      <span className="text-xs text-[var(--nash-accent)]">[{fact.domain}]</span>
                      <span className={`text-xs px-1.5 py-0.5 rounded ${typeStyle}`}>
                        {fact.fact_type}
                      </span>
                      <span className="text-xs text-[var(--nash-text-muted)]">
                        {formatRelativeTime(fact.created_at)}
                      </span>
                    </div>
                    <p className="text-[var(--nash-text)]">{fact.statement}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="text-center text-xs text-[var(--nash-text-muted)] pt-4 border-t border-[var(--nash-border)]">
        Nash Life Manager v0.2 — Phase 2 Active
      </div>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded-lg p-3 text-center hover:border-[var(--nash-accent)]/30 transition-colors">
      <p className="text-2xl text-[var(--nash-accent)] font-bold">{value}</p>
      <p className="text-xs text-[var(--nash-text-muted)] mt-1">{label}</p>
    </div>
  );
}
