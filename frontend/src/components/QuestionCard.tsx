import { useState } from 'react';
import { useAudioRecorder } from '../hooks/useAudioRecorder';
import { answerQuestion, type Question } from '../api';

interface QuestionCardProps {
  question: Question;
  onAnswered: (questionId: number) => void;
}

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

// User-friendly labels for question types
const TYPE_LABELS: Record<string, string> = {
  scaling: '1-10',
  this_or_that: 'Esto o aquello',
  last_instance: 'Ultima vez',
  quick_fact: 'Dato rapido',
  single_most: 'Lo mas importante',
  tomorrow_change: 'Cambio mañana',
  // Legacy types (in case old questions exist)
  memory_archaeology: 'Memoria',
  exception: 'Excepcion',
  parts_work: 'Partes',
  behavioral_chain: 'Cadena',
  future_self: 'Futuro',
  contrast: 'Contraste',
};

export function QuestionCard({ question, onAnswered }: QuestionCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const { isRecording, duration, startRecording, stopRecording, error } = useAudioRecorder();

  const handleRecord = async () => {
    if (isProcessing) return;

    if (isRecording) {
      const { blob } = await stopRecording();
      setIsProcessing(true);
      setResult(null);

      try {
        const response = await answerQuestion(question.id, blob);
        if (response.ok) {
          setResult(`Respondida (${response.semantic_units} unidades extraidas)`);
          onAnswered(question.id);
        } else {
          setResult(`Error: ${response.error}`);
        }
      } catch (err) {
        setResult(`Error de conexion: ${err}`);
      } finally {
        setIsProcessing(false);
      }
    } else {
      await startRecording();
    }
  };

  const isAnswered = question.was_answered === 1;

  return (
    <div className={`bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded-xl p-5 ${isAnswered ? 'opacity-60' : ''}`}>
      <p className="text-base text-[var(--nash-text)] mb-4 leading-relaxed">{question.question_text}</p>

      <div className="flex items-center justify-between">
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-sm text-[var(--nash-text-muted)] hover:text-[var(--nash-text)] transition-colors cursor-pointer"
        >
          {expanded ? 'Ocultar' : 'Ver'} por que esta pregunta
        </button>

        {!isAnswered && (
          <div className="flex items-center gap-3">
            {isRecording && (
              <span className="text-sm text-[var(--nash-error)] font-mono">{formatDuration(duration)}</span>
            )}
            {isProcessing ? (
              <div className="flex items-center gap-2 text-sm text-[var(--nash-text-muted)]">
                <div className="w-5 h-5 border-2 border-[var(--nash-text-muted)] border-t-[var(--nash-accent)] rounded-full animate-spin" />
                Procesando...
              </div>
            ) : (
              <button
                onClick={handleRecord}
                className={`flex items-center gap-2 text-base font-medium transition-colors cursor-pointer ${
                  isRecording
                    ? 'text-[var(--nash-error)] hover:opacity-80'
                    : 'text-[var(--nash-wine)] hover:opacity-80'
                }`}
              >
                {isRecording ? (
                  <>
                    <div className="w-4 h-4 rounded-sm bg-[var(--nash-error)]" />
                    Detener
                  </>
                ) : (
                  <>
                    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" />
                      <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
                    </svg>
                    Responder
                  </>
                )}
              </button>
            )}
          </div>
        )}

        {isAnswered && (
          <span className="text-sm text-[var(--nash-success)] flex items-center gap-1">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            Respondida
          </span>
        )}
      </div>

      {expanded && question.why_asked && (
        <p className="text-sm text-[var(--nash-text-muted)] mt-4 pt-4 border-t border-[var(--nash-border)]">
          {question.why_asked}
        </p>
      )}

      {result && (
        <p className={`text-sm mt-3 ${result.startsWith('Error') ? 'text-[var(--nash-error)]' : 'text-[var(--nash-success)]'}`}>
          {result}
        </p>
      )}

      {error && (
        <p className="text-sm text-[var(--nash-error)] mt-3">{error}</p>
      )}

      <div className="flex gap-2 mt-4">
        <span className="text-xs px-3 py-1 rounded-full bg-[var(--nash-prussian-soft)] text-[var(--nash-prussian)]">
          {TYPE_LABELS[question.question_type] || question.question_type}
        </span>
      </div>
    </div>
  );
}
