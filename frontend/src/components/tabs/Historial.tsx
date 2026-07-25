import { useState, useEffect } from 'react';
import { fetchDiary, fetchDiaryConversation, replyToDiaryEntry } from '../../api';
import type { DiaryConversation } from '../../api';
import { AudioPlayerRow } from '../AudioPlayerRow';
import { useAudioRecorder } from '../../hooks/useAudioRecorder';

interface DiaryEntry {
  id: number;
  timestamp: string;
  entry_type: string;
  raw_transcript: string;
  summary: string;
  energy_level: number | null;
  duration_s: number | null;
  audio_path: string | null;
  audio_play_url: string | null;
  nash_response: string | null;
}

function formatDateTime(ts: string): string {
  const d = new Date(ts + 'Z');
  return d.toLocaleString('es-MX', {
    weekday: 'short',
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatDuration(seconds: number | null): string {
  if (!seconds || seconds <= 0) return '';
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  if (m === 0) return `${s}s`;
  return `${m}m${s.toString().padStart(2, '0')}s`;
}

const TYPE_LABELS: Record<string, string> = {
  morning: 'Mañana',
  night: 'Noche',
  spontaneous: 'Espontáneo',
};

export function Historial() {
  const [entries, setEntries] = useState<DiaryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedResponses, setExpandedResponses] = useState<Set<number>>(new Set());
  const [regenerating, setRegenerating] = useState(false);
  const [conversations, setConversations] = useState<Record<number, DiaryConversation>>({});
  const [replyInputs, setReplyInputs] = useState<Record<number, string>>({});
  const [replying, setReplying] = useState<Set<number>>(new Set());
  const [recordingFor, setRecordingFor] = useState<number | null>(null);

  const { isRecording, duration, startRecording, stopRecording } = useAudioRecorder();

  const loadEntries = () => {
    setLoading(true);
    fetchDiary(50)
      .then(setEntries)
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadEntries();
  }, []);

  const toggleResponse = async (id: number) => {
    setExpandedResponses((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
        // Load conversation when expanding
        if (!conversations[id]) {
          fetchDiaryConversation(id).then((conv) => {
            setConversations((prev) => ({ ...prev, [id]: conv }));
          });
        }
      }
      return next;
    });
  };

  const handleReplyChange = (id: number, value: string) => {
    setReplyInputs((prev) => ({ ...prev, [id]: value }));
  };

  const handleReply = async (entryId: number, audioBlob?: Blob) => {
    const text = replyInputs[entryId]?.trim();
    if (!text && !audioBlob) return;

    setReplying((prev) => new Set(prev).add(entryId));

    try {
      const result = await replyToDiaryEntry(entryId, text || undefined, audioBlob);
      if (result.ok && result.conversation) {
        setConversations((prev) => ({ ...prev, [entryId]: result.conversation! }));
        setReplyInputs((prev) => ({ ...prev, [entryId]: '' }));
      }
    } catch (e) {
      console.error('Error replying:', e);
    } finally {
      setReplying((prev) => {
        const next = new Set(prev);
        next.delete(entryId);
        return next;
      });
    }
  };

  const handleMicClick = async (entryId: number) => {
    if (isRecording && recordingFor === entryId) {
      // Stop recording and send
      const { blob } = await stopRecording();
      setRecordingFor(null);
      if (blob.size > 0) {
        handleReply(entryId, blob);
      }
    } else if (!isRecording) {
      // Start recording
      setRecordingFor(entryId);
      await startRecording();
    }
  };

  const formatRecordingDuration = (seconds: number): string => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  const handleRegenerate = async () => {
    setRegenerating(true);
    try {
      const res = await fetch('/api/diary/regenerate-responses', { method: 'POST' });
      const data = await res.json();
      if (data.processed > 0) {
        loadEntries();
      }
    } catch (e) {
      console.error('Error regenerating responses:', e);
    } finally {
      setRegenerating(false);
    }
  };

  const entriesWithoutResponse = entries.filter((e) => !e.nash_response);

  return (
    <div className="max-w-3xl mx-auto px-4 py-6">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-lg font-semibold">Historial de entradas</h2>
        <div className="flex items-center gap-3">
          {entriesWithoutResponse.length > 0 && (
            <button
              onClick={handleRegenerate}
              disabled={regenerating}
              className="text-xs bg-[var(--nash-prussian-soft)] text-[var(--nash-prussian)] px-3 py-1.5 rounded-lg hover:bg-[var(--nash-prussian)]/20 disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed"
            >
              {regenerating ? 'Procesando...' : `Generar respuestas (${entriesWithoutResponse.length})`}
            </button>
          )}
          <button
            onClick={loadEntries}
            className="text-xs text-[var(--nash-accent)] hover:underline cursor-pointer"
          >
            Actualizar
          </button>
        </div>
      </div>

      {loading && (
        <p className="text-[var(--nash-text-muted)] text-sm">Cargando...</p>
      )}

      {!loading && entries.length === 0 && (
        <p className="text-[var(--nash-text-muted)] text-sm">
          No hay entradas todavía. Habla con Nash para empezar.
        </p>
      )}

      <div className="space-y-2">
        {entries.map((entry) => (
          <div
            key={entry.id}
            className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded-lg p-4 hover:border-[var(--nash-accent)]/30 transition-colors"
          >
            <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1 mb-2">
              <span className="text-sm text-[var(--nash-text)]">
                {formatDateTime(entry.timestamp)}
              </span>
              {entry.duration_s != null && entry.duration_s > 0 && (
                <span className="text-xs bg-[var(--nash-teal-soft)] text-[var(--nash-teal)] px-2 py-0.5 rounded font-medium">
                  {formatDuration(entry.duration_s)}
                </span>
              )}
              <span className="text-xs bg-[var(--nash-surface-2)] px-2 py-0.5 rounded text-[var(--nash-text-muted)]">
                {TYPE_LABELS[entry.entry_type] || entry.entry_type}
              </span>
              {entry.energy_level != null && entry.energy_level > 0 && (
                <span className="text-xs text-[var(--nash-text-muted)]">
                  Energia: {entry.energy_level}/10
                </span>
              )}
            </div>

            {entry.summary ? (
              <p className="text-sm text-[var(--nash-text)] font-medium mb-2">{entry.summary}</p>
            ) : null}

            {entry.audio_play_url && (
              <div className="mb-2">
                <AudioPlayerRow
                  src={entry.audio_play_url}
                  recordedDurationS={entry.duration_s}
                />
              </div>
            )}

            {entry.raw_transcript ? (
              <p className="text-xs text-[var(--nash-text-muted)] line-clamp-3 leading-relaxed">
                {entry.raw_transcript}
              </p>
            ) : (
              <p className="text-xs text-[var(--nash-text-muted)] italic">Sin transcripcion</p>
            )}

            {/* Nash's response section */}
            {entry.nash_response && (
              <div className="mt-3 pt-3 border-t border-[var(--nash-border)]">
                <button
                  onClick={() => toggleResponse(entry.id)}
                  className="inline-flex items-center gap-2 text-xs bg-[var(--nash-prussian-soft)] text-[var(--nash-prussian)] px-3 py-1.5 rounded-lg hover:bg-[var(--nash-prussian)]/20 cursor-pointer transition-colors"
                >
                  <span>{expandedResponses.has(entry.id) ? '-' : '+'}</span>
                  <span className="font-medium">Respuesta de Nash</span>
                </button>
                {expandedResponses.has(entry.id) && (
                  <div className="mt-3 space-y-3">
                    {/* Initial Nash response */}
                    <div className="bg-[var(--nash-prussian-soft)] rounded-lg p-3">
                      <p className="text-xs text-[var(--nash-prussian)] font-medium mb-1">Nash</p>
                      <p className="text-sm text-[var(--nash-text)] whitespace-pre-wrap leading-relaxed">
                        {entry.nash_response}
                      </p>
                    </div>

                    {/* Conversation thread */}
                    {conversations[entry.id]?.messages.map((msg, idx) => (
                      <div
                        key={idx}
                        className={`rounded-lg p-3 ${
                          msg.role === 'user'
                            ? 'bg-[var(--nash-surface-2)] ml-4'
                            : 'bg-[var(--nash-prussian-soft)]'
                        }`}
                      >
                        <p className={`text-xs font-medium mb-1 ${
                          msg.role === 'user' ? 'text-[var(--nash-text-muted)]' : 'text-[var(--nash-prussian)]'
                        }`}>
                          {msg.role === 'user' ? 'Tu' : 'Nash'}
                        </p>
                        {msg.audio_path && (
                          <div className="mb-2">
                            <AudioPlayerRow
                              src={`/media/audio/${msg.audio_path.split('/').pop()}`}
                              recordedDurationS={null}
                            />
                          </div>
                        )}
                        <p className="text-sm text-[var(--nash-text)] whitespace-pre-wrap leading-relaxed">
                          {msg.content}
                        </p>
                      </div>
                    ))}

                    {/* Reply input */}
                    {(conversations[entry.id]?.can_continue !== false) && (
                      <div className="flex gap-2 mt-3 items-center">
                        {/* Mic button */}
                        <button
                          onClick={() => handleMicClick(entry.id)}
                          disabled={replying.has(entry.id) || (isRecording && recordingFor !== entry.id)}
                          className={`
                            w-10 h-10 rounded-full flex items-center justify-center transition-all cursor-pointer
                            ${isRecording && recordingFor === entry.id
                              ? 'bg-[var(--nash-error)] text-white animate-pulse'
                              : 'bg-[var(--nash-accent-soft)] text-[var(--nash-accent)] hover:bg-[var(--nash-accent)]/30'
                            }
                            disabled:opacity-40 disabled:cursor-not-allowed
                          `}
                          title={isRecording && recordingFor === entry.id ? 'Detener grabacion' : 'Grabar respuesta'}
                        >
                          {isRecording && recordingFor === entry.id ? (
                            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                              <rect x="6" y="6" width="12" height="12" rx="2" />
                            </svg>
                          ) : (
                            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                              <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" />
                              <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
                            </svg>
                          )}
                        </button>

                        {/* Recording duration indicator */}
                        {isRecording && recordingFor === entry.id && (
                          <span className="text-sm text-[var(--nash-error)] font-mono">
                            {formatRecordingDuration(duration)}
                          </span>
                        )}

                        {/* Text input */}
                        <input
                          type="text"
                          value={replyInputs[entry.id] || ''}
                          onChange={(e) => handleReplyChange(entry.id, e.target.value)}
                          placeholder="O escribe aqui..."
                          disabled={replying.has(entry.id) || (isRecording && recordingFor === entry.id)}
                          className="flex-1 bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm text-[var(--nash-text)] placeholder-[var(--nash-text-muted)] focus:outline-none focus:border-[var(--nash-accent)] disabled:opacity-50"
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' && !e.shiftKey) {
                              e.preventDefault();
                              handleReply(entry.id);
                            }
                          }}
                        />
                        <button
                          onClick={() => handleReply(entry.id)}
                          disabled={replying.has(entry.id) || !replyInputs[entry.id]?.trim() || isRecording}
                          className="bg-[var(--nash-accent)] text-white rounded-lg px-4 py-2 text-sm font-medium hover:opacity-90 disabled:opacity-40 cursor-pointer disabled:cursor-not-allowed"
                        >
                          {replying.has(entry.id) ? '...' : 'Enviar'}
                        </button>
                      </div>
                    )}

                    {/* Conversation limit indicator */}
                    {conversations[entry.id] && (
                      <p className="text-xs text-[var(--nash-text-muted)] text-center">
                        {conversations[entry.id].message_count} / {conversations[entry.id].max_messages} mensajes
                        {!conversations[entry.id].can_continue && ' (limite alcanzado)'}
                      </p>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
