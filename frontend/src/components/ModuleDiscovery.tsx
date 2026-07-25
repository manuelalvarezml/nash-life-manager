import { useCallback, useEffect, useRef, useState } from 'react';
import {
  startModuleDiscovery,
  chatModuleDiscovery,
  endModuleDiscovery,
  type ModuleName,
  type ModuleDiscoverySession,
} from '../api';

interface ModuleDiscoveryProps {
  module: ModuleName;
  title: string;
  subtitle: string;
  onClose: () => void;
  onProfileUpdated?: () => void;
}

export function ModuleDiscovery({
  module,
  title,
  subtitle,
  onClose,
  onProfileUpdated,
}: ModuleDiscoveryProps) {
  const [session, setSession] = useState<ModuleDiscoverySession | null>(null);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [textInput, setTextInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [session?.messages, sending]);

  useEffect(() => {
    const init = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await startModuleDiscovery(module);
        if (!res.ok || !res.session) {
          setError(res.error || 'No se pudo iniciar la sesion.');
          return;
        }
        setSession(res.session);
      } catch {
        setError('No se pudo conectar con el backend.');
      } finally {
        setLoading(false);
      }
    };

    init();
  }, [module]);

  const sendTextMessage = useCallback(async () => {
    const text = textInput.trim();
    if (!session || !text || sending) {
      return;
    }

    setSending(true);
    setError(null);
    try {
      const res = await chatModuleDiscovery(module, session.id, text);
      if (!res.ok || !res.session) {
        setError(res.error || 'No se pudo enviar el mensaje.');
        return;
      }

      setSession(res.session);
      setTextInput('');
      if (res.profile_updated) {
        onProfileUpdated?.();
      }
    } catch {
      setError('Error en la conversacion.');
    } finally {
      setSending(false);
    }
  }, [module, onProfileUpdated, sending, session, textInput]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    sendTextMessage();
  };

  const handleFinish = useCallback(async () => {
    if (!session) {
      onClose();
      return;
    }

    try {
      await endModuleDiscovery(module, session.id);
    } finally {
      onClose();
    }
  }, [module, onClose, session]);

  if (loading) {
    return (
      <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center">
        <div className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded-xl p-8 text-center">
          <div className="animate-spin h-8 w-8 border-2 border-[var(--nash-accent)] border-t-transparent rounded-full mx-auto mb-3" />
          <p className="text-sm text-[var(--nash-text-muted)]">Iniciando sesion de descubrimiento...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-[var(--nash-bg)] z-50 flex flex-col">
      <div className="bg-[var(--nash-surface)] border-b border-[var(--nash-border)] px-4 py-3 flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-[var(--nash-prussian)]">{title}</h2>
          <p className="text-xs text-[var(--nash-text-muted)]">{subtitle}</p>
        </div>
        <button
          onClick={handleFinish}
          className="text-sm border border-[var(--nash-border)] text-[var(--nash-text-muted)] hover:text-[var(--nash-text)] px-3 py-1.5 rounded-lg cursor-pointer"
        >
          Terminar
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {(!session?.messages || session.messages.length === 0) && (
          <div className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded-lg p-4">
            <p className="text-sm text-[var(--nash-text-muted)]">
              Cuentame tu situacion actual y te ayudo a configurar este modulo.
            </p>
          </div>
        )}

        {session?.messages.map((msg, idx) => (
          <div key={`${msg.timestamp}-${idx}`} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className={`max-w-[85%] rounded-lg px-4 py-3 ${
                msg.role === 'user'
                  ? 'bg-[var(--nash-accent)] text-white'
                  : 'bg-[var(--nash-surface)] border border-[var(--nash-border)]'
              }`}
            >
              <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
              <p className="text-xs opacity-70 mt-1">{msg.role === 'user' ? 'Tu' : 'Nash'}</p>
            </div>
          </div>
        ))}

        {sending && (
          <div className="flex justify-start">
            <div className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded-lg px-4 py-3 text-sm text-[var(--nash-text-muted)]">
              Nash esta pensando...
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {error && (
        <div className="px-4 py-2 bg-[var(--nash-wine-soft)] border-t border-[var(--nash-border)]">
          <p className="text-sm text-[var(--nash-wine)]">{error}</p>
        </div>
      )}

      <div className="bg-[var(--nash-surface)] border-t border-[var(--nash-border)] p-4">
        <form onSubmit={handleSubmit} className="flex gap-3">
          <input
            type="text"
            value={textInput}
            onChange={(e) => setTextInput(e.target.value)}
            placeholder="Escribe aqui..."
            disabled={sending}
            className="flex-1 bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-4 py-2 text-sm"
          />
          <button
            type="submit"
            disabled={sending || !textInput.trim()}
            className="px-4 py-2 bg-[var(--nash-accent)] text-white rounded-lg text-sm font-medium hover:opacity-90 disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed"
          >
            Enviar
          </button>
        </form>
      </div>
    </div>
  );
}
