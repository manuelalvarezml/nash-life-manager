import { useState } from 'react';
import { useAudioRecorder } from '../hooks/useAudioRecorder';
import { uploadAudio, type SSEMessage } from '../api';

interface MicButtonProps {
  onTranscript: (text: string) => void;
  onResponse: (text: string) => void;
  onToolCalls: (calls: SSEMessage['calls']) => void;
  onProcessing: (processing: boolean) => void;
  threadId: string;
}

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

export function MicButton({ onTranscript, onResponse, onToolCalls, onProcessing, threadId }: MicButtonProps) {
  const { isRecording, duration, startRecording, stopRecording, error } = useAudioRecorder();
  const [processing, setProcessing] = useState(false);

  const handleClick = async () => {
    if (processing) return;

    if (isRecording) {
      const { blob, durationSeconds } = await stopRecording();
      setProcessing(true);
      onProcessing(true);

      try {
        const stream = await uploadAudio(blob, 'spontaneous', threadId, durationSeconds);
        const reader = stream.getReader();

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          if (value.type === 'transcript') onTranscript(value.text || '');
          if (value.type === 'response') onResponse(value.text || '');
          if (value.type === 'tools') onToolCalls(value.calls);
          if (value.type === 'diary') window.dispatchEvent(new Event('calendar-inbox-refresh'));
          if (value.type === 'error') onResponse(`Error: ${value.text}`);
        }
      } catch (err) {
        onResponse(`Error de conexión: ${err}`);
      } finally {
        setProcessing(false);
        onProcessing(false);
      }
    } else {
      await startRecording();
    }
  };

  return (
    <div className="flex flex-col items-center gap-4">
      <button
        onClick={handleClick}
        disabled={processing}
        className={`
          relative w-32 h-32 rounded-full transition-all duration-300 flex items-center justify-center shadow-lg
          ${processing
            ? 'bg-[var(--nash-surface-2)] cursor-wait'
            : isRecording
              ? 'bg-[var(--nash-error)]/20 border-3 border-[var(--nash-error)] animate-pulse'
              : 'bg-[var(--nash-accent-soft)] border-3 border-[var(--nash-accent)] hover:bg-[var(--nash-accent)]/30 hover:scale-105 cursor-pointer'
          }
        `}
      >
        {processing ? (
          <div className="w-10 h-10 border-3 border-[var(--nash-text-muted)] border-t-[var(--nash-accent)] rounded-full animate-spin" />
        ) : isRecording ? (
          <div className="w-10 h-10 rounded-md bg-[var(--nash-error)]" />
        ) : (
          <svg className="w-14 h-14 text-[var(--nash-accent)]" fill="currentColor" viewBox="0 0 24 24">
            <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm-1-9c0-.55.45-1 1-1s1 .45 1 1v6c0 .55-.45 1-1 1s-1-.45-1-1V5z" />
            <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
          </svg>
        )}
      </button>

      {isRecording && (
        <span className="text-lg text-[var(--nash-error)] font-mono font-semibold">{formatDuration(duration)}</span>
      )}
      {processing && (
        <span className="text-base text-[var(--nash-text-muted)]">Procesando...</span>
      )}
      {error && (
        <span className="text-base text-[var(--nash-error)]">{error}</span>
      )}
    </div>
  );
}
