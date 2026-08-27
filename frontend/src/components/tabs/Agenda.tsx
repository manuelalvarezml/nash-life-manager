import { useCallback, useEffect, useState } from 'react';
import { useAudioRecorder } from '../../hooks/useAudioRecorder';
import {
  approveCalendarSuggestion,
  dismissCalendarSuggestion,
  fetchCalendarDashboard,
  patchCalendarItem,
  submitCalendarInput,
  syncCalendarEngines,
  updateSchedulePreferences,
  type CalendarDashboard,
  type CalendarItem,
  type CalendarSuggestion,
} from '../../api';

const DAY_LABELS = ['Lun', 'Mar', 'Mie', 'Jue', 'Vie', 'Sab', 'Dom'];
const SOURCE_LABELS: Record<string, string> = {
  direct: 'Directo',
  diary: 'Diario',
  goal: 'Meta',
  exercise: 'Cuerpo',
  nutrition: 'Nutricion',
  finance: 'Dinero',
  system: 'Nash',
};
const SOURCE_STYLES: Record<string, string> = {
  direct: 'border-l-[var(--nash-brick)] bg-[var(--nash-brick-soft)]',
  diary: 'border-l-[var(--nash-wine)] bg-[var(--nash-wine-soft)]',
  goal: 'border-l-[var(--nash-prussian)] bg-[var(--nash-prussian-soft)]',
  exercise: 'border-l-[var(--nash-teal)] bg-[var(--nash-teal-soft)]',
  finance: 'border-l-[var(--nash-success)] bg-emerald-50',
};

function localDate(value: string): Date {
  return new Date(`${value.slice(0, 10)}T12:00:00`);
}

function isoDate(value: Date): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function addDays(value: string, days: number): string {
  const next = localDate(value);
  next.setDate(next.getDate() + days);
  return isoDate(next);
}

function mondayOfCurrentWeek(): string {
  const today = new Date();
  const day = (today.getDay() + 6) % 7;
  today.setDate(today.getDate() - day);
  return isoDate(today);
}

function formatTime(value?: string | null): string {
  return value?.slice(11, 16) || 'Sin hora';
}

function durationLabel(item: CalendarItem): string {
  if (!item.start_at || !item.end_at) return '';
  const minutes = Math.round((new Date(item.end_at).getTime() - new Date(item.start_at).getTime()) / 60000);
  return minutes > 0 ? `${minutes} min` : '';
}

interface SuggestionDraft {
  title: string;
  date: string;
  time: string;
  duration: string;
}

export function Agenda() {
  const [weekStart, setWeekStart] = useState(mondayOfCurrentWeek);
  const [dashboard, setDashboard] = useState<CalendarDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [command, setCommand] = useState('');
  const [resultMessage, setResultMessage] = useState('');
  const [error, setError] = useState('');
  const [editingSuggestion, setEditingSuggestion] = useState<number | null>(null);
  const [suggestionDraft, setSuggestionDraft] = useState<SuggestionDraft>({ title: '', date: '', time: '', duration: '30' });
  const [editingItem, setEditingItem] = useState<number | null>(null);
  const [itemStart, setItemStart] = useState('');
  const [showSettings, setShowSettings] = useState(false);
  const { isRecording, duration, startRecording, stopRecording, error: recorderError } = useAudioRecorder();

  const loadDashboard = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await fetchCalendarDashboard(weekStart);
      setDashboard(data);
      window.dispatchEvent(new CustomEvent('calendar-inbox-changed', { detail: data.suggestions.length }));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo cargar la agenda.');
    } finally {
      setLoading(false);
    }
  }, [weekStart]);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  const runCommand = async (audio?: Blob) => {
    if ((!command.trim() && !audio) || busy) return;
    setBusy(true);
    setError('');
    setResultMessage('');
    try {
      const result = await submitCalendarInput({ text: command, audio });
      if (!result.ok) throw new Error(result.error || 'No se pudo procesar la instruccion.');
      setCommand('');
      setResultMessage(result.message || 'Agenda actualizada.');
      await loadDashboard();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo procesar la instruccion.');
    } finally {
      setBusy(false);
    }
  };

  const handleAudio = async () => {
    if (busy) return;
    if (!isRecording) {
      await startRecording();
      return;
    }
    const recording = await stopRecording();
    await runCommand(recording.blob);
  };

  const beginSuggestionEdit = (suggestion: CalendarSuggestion) => {
    setEditingSuggestion(suggestion.id);
    setSuggestionDraft({
      title: suggestion.title,
      date: suggestion.proposed_start_at?.slice(0, 10) || dashboard?.today || '',
      time: suggestion.proposed_start_at?.slice(11, 16) || '',
      duration: String(suggestion.duration_min || 30),
    });
  };

  const approveSuggestion = async (suggestion: CalendarSuggestion, edited = false) => {
    setBusy(true);
    setError('');
    try {
      const start = edited && suggestionDraft.date && suggestionDraft.time
        ? `${suggestionDraft.date}T${suggestionDraft.time}`
        : suggestion.proposed_start_at || undefined;
      const response = await approveCalendarSuggestion(suggestion.id, edited ? {
        title: suggestionDraft.title.trim() || suggestion.title,
        proposed_start_at: start,
        duration_min: Number(suggestionDraft.duration) || 30,
        first_date: suggestionDraft.date || undefined,
        preferred_time: suggestionDraft.time || undefined,
      } : {});
      if (!response.ok) throw new Error(response.error || 'No se pudo aprobar.');
      setEditingSuggestion(null);
      setResultMessage(`Aprobado: ${suggestionDraft.title || suggestion.title}`);
      await loadDashboard();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo aprobar.');
    } finally {
      setBusy(false);
    }
  };

  const dismissSuggestion = async (suggestion: CalendarSuggestion) => {
    setBusy(true);
    try {
      await dismissCalendarSuggestion(suggestion.id);
      setResultMessage(`Descartado: ${suggestion.title}`);
      await loadDashboard();
    } finally {
      setBusy(false);
    }
  };

  const completeItem = async (item: CalendarItem) => {
    const nextStatus = item.status === 'completed' ? 'planned' : 'completed';
    await patchCalendarItem(item.id, { status: nextStatus, reason: 'Cambio rapido desde Agenda.' });
    await loadDashboard();
  };

  const saveItemStart = async (item: CalendarItem) => {
    if (!itemStart) return;
    const currentMinutes = item.start_at && item.end_at
      ? Math.max(5, Math.round((new Date(item.end_at).getTime() - new Date(item.start_at).getTime()) / 60000))
      : 30;
    const end = new Date(itemStart);
    end.setMinutes(end.getMinutes() + currentMinutes);
    const localEnd = `${isoDate(end)}T${String(end.getHours()).padStart(2, '0')}:${String(end.getMinutes()).padStart(2, '0')}`;
    await patchCalendarItem(item.id, {
      start_at: itemStart,
      end_at: localEnd,
      reason: 'Hora editada manualmente desde Agenda.',
    });
    setEditingItem(null);
    await loadDashboard();
  };

  const syncEngines = async () => {
    setBusy(true);
    try {
      await syncCalendarEngines();
      setResultMessage('Metas, Cuerpo y Dinero volvieron a revisar la agenda.');
      await loadDashboard();
    } finally {
      setBusy(false);
    }
  };

  if (loading && !dashboard) {
    return <div className="p-10 text-[var(--nash-text-muted)]">Armando tu semana...</div>;
  }

  const days = Array.from({ length: 7 }, (_, index) => addDays(weekStart, index));
  const weekTitle = `${localDate(weekStart).toLocaleDateString('es-PE', { day: 'numeric', month: 'short' })} - ${localDate(addDays(weekStart, 6)).toLocaleDateString('es-PE', { day: 'numeric', month: 'short', year: 'numeric' })}`;

  return (
    <div className="max-w-[1500px] mx-auto px-4 md:px-6 py-6 space-y-6">
      <section className="relative overflow-hidden rounded-3xl bg-[var(--nash-prussian)] text-white p-6 md:p-8 shadow-lg">
        <div className="absolute -right-16 -top-20 h-64 w-64 rounded-full border-[40px] border-white/5" />
        <div className="relative grid lg:grid-cols-[1fr_1.35fr] gap-8 items-end">
          <div>
            <p className="text-sm uppercase tracking-[0.22em] text-white/60 mb-3">Agenda viva</p>
            <h1 className="text-3xl md:text-4xl font-semibold leading-tight">Lo importante necesita tiempo real.</h1>
            <p className="mt-3 text-white/70 max-w-xl">Dile a Nash que aparecio, que cambio o que parte necesita reorganizar. Las ideas detectadas en el diario esperan tu permiso.</p>
          </div>
          <div>
            <form onSubmit={(event) => { event.preventDefault(); void runCommand(); }} className="flex flex-col sm:flex-row gap-3">
              <input
                value={command}
                onChange={(event) => setCommand(event.target.value)}
                placeholder="Ej: mañana salgo con Luis a las 7, mueve el video al viernes"
                className="flex-1 rounded-2xl border border-white/15 bg-white/10 px-5 py-4 text-white placeholder:text-white/45 outline-none focus:border-white/50"
                disabled={busy}
              />
              <button type="submit" disabled={busy || !command.trim()} className="rounded-2xl bg-[var(--nash-brick)] px-6 py-4 font-semibold disabled:opacity-40 cursor-pointer">Aplicar</button>
              <button
                type="button"
                onClick={() => void handleAudio()}
                disabled={busy}
                className={`rounded-2xl px-5 py-4 font-semibold border cursor-pointer ${isRecording ? 'bg-red-500 border-red-300 animate-pulse' : 'bg-white/10 border-white/20 hover:bg-white/20'}`}
              >
                {isRecording ? `Detener ${duration}s` : 'Hablar'}
              </button>
            </form>
            <p className="mt-3 min-h-5 text-sm text-white/65">{busy ? 'Interpretando y revisando espacios...' : resultMessage || recorderError || ''}</p>
          </div>
        </div>
      </section>

      {error && <div className="rounded-2xl border border-red-200 bg-red-50 px-5 py-4 text-[var(--nash-error)]">{error}</div>}

      <section className="grid lg:grid-cols-[minmax(0,1fr)_360px] gap-6">
        <div className="space-y-4 min-w-0">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <button onClick={() => setWeekStart(addDays(weekStart, -7))} className="rounded-xl border border-[var(--nash-border)] bg-white px-4 py-2 cursor-pointer">Anterior</button>
              <button onClick={() => setWeekStart(mondayOfCurrentWeek())} className="rounded-xl border border-[var(--nash-border)] bg-white px-4 py-2 cursor-pointer">Hoy</button>
              <button onClick={() => setWeekStart(addDays(weekStart, 7))} className="rounded-xl border border-[var(--nash-border)] bg-white px-4 py-2 cursor-pointer">Siguiente</button>
            </div>
            <div className="text-right">
              <h2 className="text-xl font-semibold text-[var(--nash-prussian)]">{weekTitle}</h2>
              <p className="text-sm text-[var(--nash-text-muted)]">{dashboard?.health.planned_count || 0} bloques, {dashboard?.health.goal_aligned_count || 0} conectados a metas</p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-7 gap-3">
            {days.map((day, index) => {
              const items = dashboard?.items.filter((item) => item.start_at?.slice(0, 10) === day) || [];
              const isToday = dashboard?.today === day;
              const overloaded = dashboard?.health.overloaded_days.includes(day);
              return (
                <article key={day} className={`min-h-56 rounded-2xl border bg-white p-3 ${isToday ? 'border-[var(--nash-brick)] shadow-md' : 'border-[var(--nash-border)]'}`}>
                  <header className="flex items-center justify-between mb-3">
                    <div>
                      <p className="text-xs uppercase tracking-wider text-[var(--nash-text-muted)]">{DAY_LABELS[index]}</p>
                      <p className={`text-2xl font-semibold ${isToday ? 'text-[var(--nash-brick)]' : 'text-[var(--nash-prussian)]'}`}>{localDate(day).getDate()}</p>
                    </div>
                    <span className={`text-xs ${overloaded ? 'text-[var(--nash-error)]' : 'text-[var(--nash-text-muted)]'}`}>{dashboard?.health.minutes_by_day[day] || 0}m</span>
                  </header>
                  <div className="space-y-2">
                    {items.map((item) => (
                      <div key={item.id} className={`rounded-xl border-l-4 p-3 ${SOURCE_STYLES[item.source_kind] || 'border-l-slate-400 bg-slate-50'} ${item.status === 'completed' ? 'opacity-50' : ''} ${dashboard?.health.conflict_item_ids?.includes(item.id) ? 'ring-2 ring-red-300' : ''}`}>
                        <button onClick={() => void completeItem(item)} className="w-full text-left cursor-pointer">
                          <p className="text-xs font-semibold text-[var(--nash-text-muted)]">{formatTime(item.start_at)} {durationLabel(item) && `· ${durationLabel(item)}`}</p>
                          <p className={`mt-1 text-sm font-semibold leading-snug ${item.status === 'completed' ? 'line-through' : ''}`}>{item.title}</p>
                          <p className="mt-1 text-[11px] text-[var(--nash-text-muted)]">{SOURCE_LABELS[item.source_kind] || item.source_kind} · {item.flexibility === 'fixed' ? 'fijo' : 'movible'}</p>
                          {dashboard?.health.conflict_item_ids?.includes(item.id) && <p className="mt-1 text-[11px] font-semibold text-[var(--nash-error)]">Se cruza con otro bloque</p>}
                        </button>
                        {editingItem === item.id ? (
                          <div className="mt-2 space-y-2">
                            <input type="datetime-local" value={itemStart} onChange={(event) => setItemStart(event.target.value)} className="w-full rounded-lg border border-[var(--nash-border)] px-2 py-1 text-xs" />
                            <div className="flex gap-2">
                              <button onClick={() => void saveItemStart(item)} className="text-xs font-semibold text-[var(--nash-teal)] cursor-pointer">Guardar</button>
                              <button onClick={() => setEditingItem(null)} className="text-xs text-[var(--nash-text-muted)] cursor-pointer">Cancelar</button>
                            </div>
                          </div>
                        ) : (
                          <button onClick={() => { setEditingItem(item.id); setItemStart(item.start_at?.slice(0, 16) || ''); }} className="mt-2 text-[11px] text-[var(--nash-text-muted)] hover:text-[var(--nash-text)] cursor-pointer">Editar hora</button>
                        )}
                      </div>
                    ))}
                    {!items.length && <p className="pt-8 text-center text-xs text-[var(--nash-text-muted)]">Espacio abierto</p>}
                  </div>
                </article>
              );
            })}
          </div>

          {!!dashboard?.unscheduled.length && (
            <section className="rounded-2xl border border-dashed border-[var(--nash-border)] bg-white/60 p-5">
              <h3 className="font-semibold text-[var(--nash-prussian)]">Sin hora todavia</h3>
              <div className="mt-3 flex flex-wrap gap-2">
                {dashboard.unscheduled.map((item) => <span key={item.id} className="rounded-full bg-white border border-[var(--nash-border)] px-3 py-2 text-sm">{item.title}</span>)}
              </div>
            </section>
          )}
        </div>

        <aside className="space-y-5">
          <section className="rounded-3xl border border-[var(--nash-border)] bg-white p-5 shadow-sm">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-[0.18em] text-[var(--nash-wine)]">Bandeja de decisiones</p>
                <h2 className="mt-1 text-xl font-semibold text-[var(--nash-prussian)]">{dashboard?.suggestions.length || 0} sugerencias</h2>
              </div>
              <button onClick={() => void syncEngines()} disabled={busy} className="text-xs text-[var(--nash-teal)] cursor-pointer disabled:opacity-40">Revisar motores</button>
            </div>
            <p className="mt-2 text-sm text-[var(--nash-text-muted)]">Nada entra a tu agenda desde el diario o los otros motores sin que lo veas aqui.</p>
            <div className="mt-4 space-y-3 max-h-[650px] overflow-y-auto pr-1">
              {dashboard?.suggestions.map((suggestion) => (
                <article key={suggestion.id} className="rounded-2xl border border-[var(--nash-border)] bg-[var(--nash-bg)] p-4">
                  <div className="flex items-center justify-between gap-2">
                    <span className="rounded-full bg-white px-2.5 py-1 text-[11px] font-semibold text-[var(--nash-wine)]">{SOURCE_LABELS[suggestion.source_kind] || suggestion.source_kind}</span>
                    <span className="text-xs text-[var(--nash-text-muted)]">{suggestion.recurrence ? 'Recurrente' : formatTime(suggestion.proposed_start_at)}</span>
                  </div>
                  {editingSuggestion === suggestion.id ? (
                    <div className="mt-3 space-y-2">
                      <input value={suggestionDraft.title} onChange={(event) => setSuggestionDraft((draft) => ({ ...draft, title: event.target.value }))} className="w-full rounded-xl border border-[var(--nash-border)] bg-white px-3 py-2 text-sm" />
                      <div className="grid grid-cols-2 gap-2">
                        <input type="date" value={suggestionDraft.date} onChange={(event) => setSuggestionDraft((draft) => ({ ...draft, date: event.target.value }))} className="rounded-xl border border-[var(--nash-border)] bg-white px-3 py-2 text-sm" />
                        <input type="time" value={suggestionDraft.time} onChange={(event) => setSuggestionDraft((draft) => ({ ...draft, time: event.target.value }))} className="rounded-xl border border-[var(--nash-border)] bg-white px-3 py-2 text-sm" />
                      </div>
                      <input type="number" min="5" step="5" value={suggestionDraft.duration} onChange={(event) => setSuggestionDraft((draft) => ({ ...draft, duration: event.target.value }))} className="w-full rounded-xl border border-[var(--nash-border)] bg-white px-3 py-2 text-sm" placeholder="Duracion en minutos" />
                      <div className="flex gap-2 pt-1">
                        <button onClick={() => void approveSuggestion(suggestion, true)} className="flex-1 rounded-xl bg-[var(--nash-teal)] px-3 py-2 text-sm font-semibold text-white cursor-pointer">Guardar y aprobar</button>
                        <button onClick={() => setEditingSuggestion(null)} className="px-2 text-sm text-[var(--nash-text-muted)] cursor-pointer">Cerrar</button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <h3 className="mt-3 font-semibold leading-snug">{suggestion.title}</h3>
                      {suggestion.description && <p className="mt-1 text-sm text-[var(--nash-text-muted)] line-clamp-3">{suggestion.description}</p>}
                      <p className="mt-2 text-xs text-[var(--nash-text-muted)]">{suggestion.duration_min || 30} min · prioridad {suggestion.priority}</p>
                      {suggestion.rationale && <p className="mt-2 text-xs italic text-[var(--nash-text-muted)]">{suggestion.rationale}</p>}
                      <div className="mt-3 grid grid-cols-3 gap-2">
                        <button onClick={() => void approveSuggestion(suggestion)} disabled={busy} className="rounded-xl bg-[var(--nash-success)] px-2 py-2 text-xs font-semibold text-white cursor-pointer">Aprobar</button>
                        <button onClick={() => beginSuggestionEdit(suggestion)} className="rounded-xl border border-[var(--nash-border)] bg-white px-2 py-2 text-xs font-semibold cursor-pointer">Editar</button>
                        <button onClick={() => void dismissSuggestion(suggestion)} disabled={busy} className="rounded-xl px-2 py-2 text-xs text-[var(--nash-error)] cursor-pointer">Eliminar</button>
                      </div>
                    </>
                  )}
                </article>
              ))}
              {!dashboard?.suggestions.length && <p className="py-8 text-center text-sm text-[var(--nash-text-muted)]">No hay decisiones pendientes.</p>}
            </div>
          </section>

          <section className="rounded-2xl border border-[var(--nash-border)] bg-white p-5">
            <button onClick={() => setShowSettings((value) => !value)} className="flex w-full items-center justify-between font-semibold text-[var(--nash-prussian)] cursor-pointer">
              Limites realistas
              <span>{showSettings ? '−' : '+'}</span>
            </button>
            {showSettings && dashboard && (
              <div className="mt-4 space-y-3">
                <label className="block text-xs text-[var(--nash-text-muted)]">Mi dia puede empezar
                  <input type="time" value={dashboard.preferences.day_start_time} onChange={(event) => setDashboard({ ...dashboard, preferences: { ...dashboard.preferences, day_start_time: event.target.value } })} className="mt-1 w-full rounded-xl border border-[var(--nash-border)] px-3 py-2 text-sm" />
                </label>
                <label className="block text-xs text-[var(--nash-text-muted)]">Mi dia debe terminar
                  <input type="time" value={dashboard.preferences.day_end_time} onChange={(event) => setDashboard({ ...dashboard, preferences: { ...dashboard.preferences, day_end_time: event.target.value } })} className="mt-1 w-full rounded-xl border border-[var(--nash-border)] px-3 py-2 text-sm" />
                </label>
                <label className="block text-xs text-[var(--nash-text-muted)]">Maximo planificado por dia (min)
                  <input type="number" min="60" max="900" step="30" value={dashboard.preferences.max_scheduled_min_per_day} onChange={(event) => setDashboard({ ...dashboard, preferences: { ...dashboard.preferences, max_scheduled_min_per_day: Number(event.target.value) } })} className="mt-1 w-full rounded-xl border border-[var(--nash-border)] px-3 py-2 text-sm" />
                </label>
                <button onClick={async () => { await updateSchedulePreferences(dashboard.preferences); setResultMessage('Limites actualizados.'); await loadDashboard(); }} className="w-full rounded-xl bg-[var(--nash-prussian)] px-4 py-2 text-sm font-semibold text-white cursor-pointer">Guardar limites</button>
              </div>
            )}
          </section>
        </aside>
      </section>
    </div>
  );
}
