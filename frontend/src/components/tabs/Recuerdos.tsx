import { useCallback, useEffect, useState } from 'react';
import {
  createMemory,
  deleteMemory,
  fetchMemories,
  patchMemory,
  type StructuredMemory,
} from '../../api';

interface MemoryDraft {
  title: string;
  raw_transcript: string;
  occurred_year_start: string;
  occurred_year_end: string;
  age_start: string;
  age_end: string;
  place_name: string;
  people: string;
  themes: string;
  emotional_valence: string;
  memory_type: string;
  significance: string;
  sensory_details: string;
  notes: string;
  user_verified: boolean;
}

const EMPTY_DRAFT: MemoryDraft = {
  title: '',
  raw_transcript: '',
  occurred_year_start: '',
  occurred_year_end: '',
  age_start: '',
  age_end: '',
  place_name: '',
  people: '',
  themes: '',
  emotional_valence: '',
  memory_type: '',
  significance: '',
  sensory_details: '',
  notes: '',
  user_verified: false,
};

function memoryToDraft(memory: StructuredMemory): MemoryDraft {
  return {
    title: memory.title || memory.topic || '',
    raw_transcript: memory.raw_transcript || '',
    occurred_year_start: memory.occurred_year_start?.toString() || '',
    occurred_year_end: memory.occurred_year_end?.toString() || '',
    age_start: memory.age_start?.toString() || '',
    age_end: memory.age_end?.toString() || '',
    place_name: memory.place_name || '',
    people: (memory.people || []).join(', '),
    themes: (memory.themes || []).join(', '),
    emotional_valence: memory.emotional_valence || '',
    memory_type: memory.memory_type || '',
    significance: memory.significance?.toString() || '',
    sensory_details: memory.sensory_details || '',
    notes: memory.notes || '',
    user_verified: Boolean(memory.user_verified),
  };
}

function draftPayload(draft: MemoryDraft): Partial<StructuredMemory> {
  const numberOrNull = (value: string) => value.trim() ? Number(value) : null;
  return {
    title: draft.title.trim(),
    raw_transcript: draft.raw_transcript.trim(),
    occurred_year_start: numberOrNull(draft.occurred_year_start),
    occurred_year_end: numberOrNull(draft.occurred_year_end),
    age_start: numberOrNull(draft.age_start),
    age_end: numberOrNull(draft.age_end),
    place_name: draft.place_name.trim() || null,
    people: draft.people.split(',').map((value) => value.trim()).filter(Boolean),
    themes: draft.themes.split(',').map((value) => value.trim()).filter(Boolean),
    emotional_valence: draft.emotional_valence || null,
    memory_type: draft.memory_type || null,
    significance: numberOrNull(draft.significance),
    sensory_details: draft.sensory_details.trim() || null,
    notes: draft.notes.trim() || null,
    user_verified: draft.user_verified ? 1 : 0,
  };
}

function yearsLabel(memory: StructuredMemory): string {
  if (memory.occurred_year_start && memory.occurred_year_end && memory.occurred_year_start !== memory.occurred_year_end) {
    return `${memory.occurred_year_start}-${memory.occurred_year_end}`;
  }
  return memory.occurred_year_start?.toString() || memory.occurred_year_end?.toString() || 'Sin fecha';
}

function ageLabel(memory: StructuredMemory): string {
  if (memory.age_start != null && memory.age_end != null && memory.age_start !== memory.age_end) {
    return `${memory.age_start}-${memory.age_end} anos`;
  }
  return memory.age_start != null ? `${memory.age_start} anos` : 'Edad incierta';
}

export function Recuerdos() {
  const [memories, setMemories] = useState<StructuredMemory[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [archiveOpen, setArchiveOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | 'new' | null>(null);
  const [draft, setDraft] = useState<MemoryDraft>(EMPTY_DRAFT);
  const [error, setError] = useState('');

  const loadMemories = useCallback(async (query?: string) => {
    setLoading(true);
    setError('');
    try {
      const data = await fetchMemories(query);
      setMemories(data.memories || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudieron cargar los recuerdos.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadMemories();
  }, [loadMemories]);

  const openEditor = (memory?: StructuredMemory) => {
    if (memory) {
      setEditingId(memory.id);
      setDraft(memoryToDraft(memory));
    } else {
      setEditingId('new');
      setDraft(EMPTY_DRAFT);
    }
  };

  const saveMemory = async () => {
    if (!draft.title.trim() && !draft.raw_transcript.trim()) {
      setError('Escribe al menos un titulo o el contenido del recuerdo.');
      return;
    }
    const payload = draftPayload(draft);
    const result = editingId === 'new'
      ? await createMemory(payload)
      : await patchMemory(Number(editingId), payload);
    if (!result.ok) {
      setError(result.error || 'No se pudo guardar el recuerdo.');
      return;
    }
    setEditingId(null);
    await loadMemories(search);
  };

  const removeMemory = async (memory: StructuredMemory) => {
    if (!window.confirm(`Eliminar "${memory.title || memory.topic}"? Esta accion no se puede deshacer desde la app.`)) return;
    await deleteMemory(memory.id);
    await loadMemories(search);
  };

  return (
    <div className="max-w-7xl mx-auto px-4 md:px-6 py-8 space-y-6">
      <section className="grid lg:grid-cols-[1.15fr_0.85fr] gap-6 items-stretch">
        <div className="rounded-3xl bg-[var(--nash-wine)] text-white p-7 md:p-10 relative overflow-hidden">
          <div className="absolute right-0 bottom-0 h-52 w-52 translate-x-16 translate-y-20 rounded-full border-[32px] border-white/5" />
          <p className="text-sm uppercase tracking-[0.22em] text-white/60">Memoria autobiografica</p>
          <h1 className="mt-4 text-3xl md:text-4xl font-semibold max-w-2xl">Un lugar para lo que no quieres perder de ti.</h1>
          <p className="mt-4 max-w-2xl text-white/75">Cuando una entrada del diario contiene un recuerdo, Nash conserva el episodio y sus pistas: edad, anos posibles, lugar, personas, emociones y detalles sensoriales. Puedes corregir cualquier inferencia.</p>
          <div className="mt-7 flex flex-wrap gap-3">
            <button onClick={() => setArchiveOpen(true)} className="rounded-2xl bg-white px-5 py-3 font-semibold text-[var(--nash-wine)] cursor-pointer">Abrir archivo cronologico</button>
            <button onClick={() => openEditor()} className="rounded-2xl border border-white/30 px-5 py-3 font-semibold text-white cursor-pointer">Agregar manualmente</button>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div className="rounded-3xl border border-[var(--nash-border)] bg-white p-6">
            <p className="text-4xl font-semibold text-[var(--nash-prussian)]">{memories.length}</p>
            <p className="mt-2 text-sm text-[var(--nash-text-muted)]">recuerdos preservados</p>
          </div>
          <div className="rounded-3xl border border-[var(--nash-border)] bg-white p-6">
            <p className="text-4xl font-semibold text-[var(--nash-teal)]">{memories.filter((memory) => memory.user_verified).length}</p>
            <p className="mt-2 text-sm text-[var(--nash-text-muted)]">revisados por ti</p>
          </div>
          <div className="col-span-2 rounded-3xl border border-[var(--nash-border)] bg-white p-6">
            <p className="text-xs uppercase tracking-[0.18em] text-[var(--nash-text-muted)]">Como calcula los anos</p>
            <p className="mt-2 text-sm leading-relaxed">Si dices “cuando tenia 12”, Nash usa tu fecha de nacimiento localmente y guarda un rango de anos posible. Si dices un ano exacto, ese dato tiene prioridad. La incertidumbre queda visible, no escondida.</p>
          </div>
        </div>
      </section>

      {error && <div className="rounded-2xl border border-red-200 bg-red-50 px-5 py-4 text-[var(--nash-error)]">{error}</div>}

      {archiveOpen && (
        <section className="rounded-3xl border border-[var(--nash-border)] bg-white overflow-hidden shadow-sm">
          <header className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[var(--nash-border)] p-5">
            <div>
              <h2 className="text-xl font-semibold text-[var(--nash-prussian)]">Archivo: presente hacia el pasado</h2>
              <p className="mt-1 text-sm text-[var(--nash-text-muted)]">Las filas sin fecha quedan al final hasta que aparezca una pista.</p>
            </div>
            <div className="flex gap-2">
              <form onSubmit={(event) => { event.preventDefault(); void loadMemories(search); }} className="flex gap-2">
                <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Buscar lugar, persona, tema..." className="w-full md:w-72 rounded-xl border border-[var(--nash-border)] px-4 py-2 text-sm" />
                <button className="rounded-xl bg-[var(--nash-prussian)] px-4 py-2 text-sm font-semibold text-white cursor-pointer">Buscar</button>
              </form>
              <button onClick={() => setArchiveOpen(false)} className="rounded-xl px-3 text-[var(--nash-text-muted)] cursor-pointer">Cerrar</button>
            </div>
          </header>

          <div className="overflow-x-auto">
            <table className="w-full min-w-[1050px] border-collapse text-left">
              <thead className="bg-[var(--nash-bg)] text-xs uppercase tracking-wider text-[var(--nash-text-muted)]">
                <tr>
                  <th className="px-5 py-4">Anos / edad</th>
                  <th className="px-5 py-4">Recuerdo</th>
                  <th className="px-5 py-4">Lugar</th>
                  <th className="px-5 py-4">Personas y temas</th>
                  <th className="px-5 py-4">Lectura</th>
                  <th className="px-5 py-4">Estado</th>
                  <th className="px-5 py-4" />
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--nash-border)]">
                {memories.map((memory) => (
                  <tr key={memory.id} className="align-top hover:bg-[var(--nash-bg)]/60">
                    <td className="px-5 py-5 whitespace-nowrap">
                      <p className="font-semibold text-[var(--nash-prussian)]">{yearsLabel(memory)}</p>
                      <p className="mt-1 text-xs text-[var(--nash-text-muted)]">{ageLabel(memory)}</p>
                    </td>
                    <td className="px-5 py-5 max-w-md">
                      <p className="font-semibold">{memory.title || memory.topic}</p>
                      <p className="mt-1 text-sm leading-relaxed text-[var(--nash-text-muted)] line-clamp-3">{memory.raw_transcript}</p>
                      {memory.sensory_details && <p className="mt-2 text-xs italic text-[var(--nash-wine)]">Detalle: {memory.sensory_details}</p>}
                    </td>
                    <td className="px-5 py-5 text-sm">{memory.place_name || '—'}</td>
                    <td className="px-5 py-5 max-w-xs">
                      <p className="text-sm">{memory.people?.join(', ') || '—'}</p>
                      <div className="mt-2 flex flex-wrap gap-1">
                        {memory.themes?.map((theme) => <span key={theme} className="rounded-full bg-[var(--nash-prussian-soft)] px-2 py-1 text-[11px] text-[var(--nash-prussian)]">{theme}</span>)}
                      </div>
                    </td>
                    <td className="px-5 py-5 text-sm">
                      <p>{memory.memory_type || 'tipo abierto'}</p>
                      <p className="mt-1 text-xs text-[var(--nash-text-muted)]">{memory.emotional_valence || 'emocion abierta'}{memory.significance ? ` · importancia ${memory.significance}/5` : ''}</p>
                    </td>
                    <td className="px-5 py-5">
                      <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${memory.user_verified ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>{memory.user_verified ? 'Revisado' : 'Por revisar'}</span>
                    </td>
                    <td className="px-5 py-5 whitespace-nowrap">
                      <button onClick={() => openEditor(memory)} className="text-sm font-semibold text-[var(--nash-teal)] cursor-pointer">Editar</button>
                      <button onClick={() => void removeMemory(memory)} className="ml-3 text-sm text-[var(--nash-error)] cursor-pointer">Eliminar</button>
                    </td>
                  </tr>
                ))}
                {!loading && !memories.length && (
                  <tr><td colSpan={7} className="px-5 py-16 text-center text-[var(--nash-text-muted)]">Aun no hay recuerdos para esta busqueda.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {editingId !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4" onMouseDown={() => setEditingId(null)}>
          <section className="max-h-[92vh] w-full max-w-4xl overflow-y-auto rounded-3xl bg-white p-6 md:p-8 shadow-2xl" onMouseDown={(event) => event.stopPropagation()}>
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.18em] text-[var(--nash-wine)]">{editingId === 'new' ? 'Nuevo recuerdo' : 'Corregir recuerdo'}</p>
                <h2 className="mt-1 text-2xl font-semibold text-[var(--nash-prussian)]">La version que quieres conservar</h2>
              </div>
              <button onClick={() => setEditingId(null)} className="text-2xl text-[var(--nash-text-muted)] cursor-pointer">×</button>
            </div>
            <div className="mt-6 grid md:grid-cols-2 gap-4">
              <label className="md:col-span-2 text-sm">Titulo
                <input value={draft.title} onChange={(event) => setDraft({ ...draft, title: event.target.value })} className="mt-1 w-full rounded-xl border border-[var(--nash-border)] px-4 py-3" />
              </label>
              <label className="md:col-span-2 text-sm">Lo que recuerdas
                <textarea value={draft.raw_transcript} onChange={(event) => setDraft({ ...draft, raw_transcript: event.target.value })} rows={5} className="mt-1 w-full rounded-xl border border-[var(--nash-border)] px-4 py-3" />
              </label>
              <div className="grid grid-cols-2 gap-3">
                <label className="text-sm">Ano inicio<input type="number" value={draft.occurred_year_start} onChange={(event) => setDraft({ ...draft, occurred_year_start: event.target.value })} className="mt-1 w-full rounded-xl border border-[var(--nash-border)] px-3 py-2" /></label>
                <label className="text-sm">Ano fin<input type="number" value={draft.occurred_year_end} onChange={(event) => setDraft({ ...draft, occurred_year_end: event.target.value })} className="mt-1 w-full rounded-xl border border-[var(--nash-border)] px-3 py-2" /></label>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <label className="text-sm">Edad inicio<input type="number" value={draft.age_start} onChange={(event) => setDraft({ ...draft, age_start: event.target.value })} className="mt-1 w-full rounded-xl border border-[var(--nash-border)] px-3 py-2" /></label>
                <label className="text-sm">Edad fin<input type="number" value={draft.age_end} onChange={(event) => setDraft({ ...draft, age_end: event.target.value })} className="mt-1 w-full rounded-xl border border-[var(--nash-border)] px-3 py-2" /></label>
              </div>
              <label className="text-sm">Lugar<input value={draft.place_name} onChange={(event) => setDraft({ ...draft, place_name: event.target.value })} className="mt-1 w-full rounded-xl border border-[var(--nash-border)] px-4 py-3" /></label>
              <label className="text-sm">Personas, separadas por coma<input value={draft.people} onChange={(event) => setDraft({ ...draft, people: event.target.value })} className="mt-1 w-full rounded-xl border border-[var(--nash-border)] px-4 py-3" /></label>
              <label className="text-sm">Temas, separados por coma<input value={draft.themes} onChange={(event) => setDraft({ ...draft, themes: event.target.value })} className="mt-1 w-full rounded-xl border border-[var(--nash-border)] px-4 py-3" /></label>
              <label className="text-sm">Tipo
                <select value={draft.memory_type} onChange={(event) => setDraft({ ...draft, memory_type: event.target.value })} className="mt-1 w-full rounded-xl border border-[var(--nash-border)] px-4 py-3">
                  <option value="">Sin clasificar</option><option value="evento">Evento</option><option value="etapa">Etapa</option><option value="persona">Persona</option><option value="lugar">Lugar</option><option value="logro">Logro</option><option value="perdida">Perdida</option><option value="cotidiano">Cotidiano</option>
                </select>
              </label>
              <label className="text-sm">Emocion
                <select value={draft.emotional_valence} onChange={(event) => setDraft({ ...draft, emotional_valence: event.target.value })} className="mt-1 w-full rounded-xl border border-[var(--nash-border)] px-4 py-3">
                  <option value="">Sin clasificar</option><option value="positive">Positiva</option><option value="negative">Negativa</option><option value="conflicted">Mixta</option><option value="neutral">Neutral</option>
                </select>
              </label>
              <label className="text-sm">Importancia 1-5<input type="number" min="1" max="5" value={draft.significance} onChange={(event) => setDraft({ ...draft, significance: event.target.value })} className="mt-1 w-full rounded-xl border border-[var(--nash-border)] px-4 py-3" /></label>
              <label className="md:col-span-2 text-sm">Detalles sensoriales<textarea value={draft.sensory_details} onChange={(event) => setDraft({ ...draft, sensory_details: event.target.value })} rows={2} className="mt-1 w-full rounded-xl border border-[var(--nash-border)] px-4 py-3" /></label>
              <label className="md:col-span-2 text-sm">Notas tuyas<textarea value={draft.notes} onChange={(event) => setDraft({ ...draft, notes: event.target.value })} rows={2} className="mt-1 w-full rounded-xl border border-[var(--nash-border)] px-4 py-3" /></label>
              <label className="md:col-span-2 flex items-center gap-3 rounded-xl bg-[var(--nash-bg)] px-4 py-3 text-sm"><input type="checkbox" checked={draft.user_verified} onChange={(event) => setDraft({ ...draft, user_verified: event.target.checked })} /> Confirmo que revise estos datos</label>
            </div>
            <div className="mt-6 flex justify-end gap-3">
              <button onClick={() => setEditingId(null)} className="rounded-xl px-5 py-3 text-[var(--nash-text-muted)] cursor-pointer">Cancelar</button>
              <button onClick={() => void saveMemory()} className="rounded-xl bg-[var(--nash-wine)] px-6 py-3 font-semibold text-white cursor-pointer">Guardar recuerdo</button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
