import { useState, useCallback, useEffect } from 'react';
import { MicButton } from '../MicButton';
import { StreamResponse } from '../StreamResponse';
import { QuestionCard } from '../QuestionCard';
import {
  sendChat,
  fetchTodaysQuestions,
  generateQuestions,
  type SSEMessage,
  type Question,
} from '../../api';

interface HomeProps {
  threadId: string;
}

export function Home({ threadId }: HomeProps) {
  const [transcript, setTranscript] = useState('');
  const [response, setResponse] = useState('');
  const [toolCalls, setToolCalls] = useState<SSEMessage['calls']>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [textInput, setTextInput] = useState('');
  const [questions, setQuestions] = useState<Question[]>([]);
  const [questionsLoading, setQuestionsLoading] = useState(true);
  const [questionsError, setQuestionsError] = useState<string | null>(null);
  const [generatingQuestions, setGeneratingQuestions] = useState(false);
  const [showQuestions, setShowQuestions] = useState(false);

  const loadQuestions = useCallback(async () => {
    setQuestionsLoading(true);
    setQuestionsError(null);
    try {
      const data = await fetchTodaysQuestions();
      setQuestions(data.questions || []);
    } catch {
      setQuestionsError('No pude cargar preguntas hoy.');
    } finally {
      setQuestionsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadQuestions();
  }, [loadQuestions]);

  const handleGenerateQuestions = useCallback(async () => {
    setGeneratingQuestions(true);
    setQuestionsError(null);
    try {
      const data = await generateQuestions();
      setQuestions(data.questions || []);
      if (!data.questions?.length) {
        setQuestionsError('No se pudieron generar preguntas ahora. Intenta de nuevo.');
      }
    } catch {
      setQuestionsError('No se pudieron generar preguntas ahora. Revisa el backend/Ollama.');
    } finally {
      setGeneratingQuestions(false);
      await loadQuestions();
    }
  }, [loadQuestions]);

  const handleQuestionAnswered = useCallback((questionId: number) => {
    setQuestions((prev) =>
      prev.map((q) => (q.id === questionId ? { ...q, was_answered: 1 } : q))
    );
  }, []);

  const handleTranscript = useCallback((text: string) => {
    setTranscript(text);
    setResponse('');
    setToolCalls([]);
  }, []);

  const handleResponse = useCallback((text: string) => {
    setResponse(text);
  }, []);

  const handleToolCalls = useCallback((calls: SSEMessage['calls']) => {
    setToolCalls(calls || []);
  }, []);

  const handleTextSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!textInput.trim() || isProcessing) return;

    const text = textInput.trim();
    setTextInput('');
    setTranscript(text);
    setResponse('');
    setToolCalls([]);
    setIsProcessing(true);

    try {
      const stream = await sendChat(text, threadId);
      const reader = stream.getReader();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        if (value.type === 'response') setResponse(value.text || '');
        if (value.type === 'tools') setToolCalls(value.calls || []);
        if (value.type === 'error') setResponse(`Error: ${value.text}`);
      }
    } catch (err) {
      setResponse(`Error de conexion: ${err}`);
    } finally {
      setIsProcessing(false);
    }
  };

  const unansweredCount = questions.filter(q => q.was_answered === 0).length;

  return (
    <div className="flex min-h-[calc(100vh-65px)]">
      {/* Main content area */}
      <div className={`flex-1 flex flex-col items-center gap-10 px-6 py-10 transition-all duration-300 ${showQuestions ? 'mr-0' : ''}`}>
        <div className="text-center">
          <h1 className="text-3xl font-semibold mb-2 text-[var(--nash-prussian)]">Nash</h1>
          <p className="text-base text-[var(--nash-text-muted)]">
            Tu companero de vida. Habla o escribe.
          </p>
        </div>

        {/* Toggle questions button */}
        <button
          onClick={() => setShowQuestions(!showQuestions)}
          className={`
            flex items-center gap-2 px-5 py-3 rounded-xl font-medium transition-all cursor-pointer
            ${showQuestions
              ? 'bg-[var(--nash-teal)] text-white'
              : 'bg-[var(--nash-teal-soft)] text-[var(--nash-teal)] border border-[var(--nash-teal)]'
            }
          `}
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          {showQuestions ? 'Ocultar preguntas' : `Preguntas de hoy${unansweredCount > 0 ? ` (${unansweredCount})` : ''}`}
        </button>

        <MicButton
          onTranscript={handleTranscript}
          onResponse={handleResponse}
          onToolCalls={handleToolCalls}
          onProcessing={setIsProcessing}
          threadId={threadId}
        />

        <form onSubmit={handleTextSubmit} className="w-full max-w-xl">
          <div className="flex gap-3">
            <input
              type="text"
              value={textInput}
              onChange={(e) => setTextInput(e.target.value)}
              placeholder="O escribe aqui..."
              disabled={isProcessing}
              className="flex-1 bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded-xl px-5 py-4 text-base text-[var(--nash-text)] placeholder-[var(--nash-text-muted)] focus:outline-none focus:border-[var(--nash-accent)] transition-colors"
            />
            <button
              type="submit"
              disabled={isProcessing || !textInput.trim()}
              className="bg-[var(--nash-accent)] text-white rounded-xl px-6 py-4 text-base font-medium hover:opacity-90 disabled:opacity-40 transition-all cursor-pointer disabled:cursor-not-allowed"
            >
              Enviar
            </button>
          </div>
        </form>

        <StreamResponse
          transcript={transcript}
          response={response}
          toolCalls={toolCalls || []}
          isProcessing={isProcessing}
        />
      </div>

      {/* Questions panel - toggleable right column */}
      <div
        className={`
          fixed right-0 top-[65px] h-[calc(100vh-65px)] w-[40%] max-w-md
          bg-[var(--nash-surface)] border-l border-[var(--nash-border)] shadow-lg
          transform transition-transform duration-300 ease-in-out overflow-y-auto
          ${showQuestions ? 'translate-x-0' : 'translate-x-full'}
        `}
      >
        <div className="p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold text-[var(--nash-prussian)]">Preguntas de hoy</h2>
            <button
              onClick={() => setShowQuestions(false)}
              className="p-2 rounded-lg hover:bg-[var(--nash-surface-2)] transition-colors cursor-pointer"
            >
              <svg className="w-5 h-5 text-[var(--nash-text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <button
            type="button"
            onClick={handleGenerateQuestions}
            disabled={generatingQuestions}
            className="w-full text-sm text-[var(--nash-teal)] hover:text-[var(--nash-text)] disabled:opacity-50 transition-colors cursor-pointer disabled:cursor-not-allowed py-2 rounded-lg border border-[var(--nash-teal)] hover:bg-[var(--nash-teal-soft)]"
          >
            {generatingQuestions ? 'Generando...' : 'Generar nuevas preguntas'}
          </button>

          {questionsLoading && (
            <p className="text-base text-[var(--nash-text-muted)]">Cargando preguntas...</p>
          )}
          {!questionsLoading && questions.length === 0 && !questionsError && (
            <p className="text-base text-[var(--nash-text-muted)]">
              Aun no hay preguntas para hoy. Pulsa "Generar nuevas preguntas".
            </p>
          )}
          {!questionsLoading && questionsError && (
            <p className="text-base text-[var(--nash-warning)]">{questionsError}</p>
          )}

          <div className="space-y-3">
            {!questionsLoading && questions.length > 0 && questions.map((q) => (
              <QuestionCard
                key={q.id}
                question={q}
                onAnswered={handleQuestionAnswered}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
