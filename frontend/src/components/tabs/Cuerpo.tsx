import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  createNutritionEntry,
  createWorkoutSession,
  fetchExerciseProfile,
  fetchNutritionEntries,
  fetchNutritionProfile,
  fetchWorkoutSessions,
  fetchWorkoutTemplates,
  type ExerciseProfile,
  type FoodEntry,
  type NutritionDailyTotals,
  type NutritionProfile,
  type WorkoutSession,
  type WorkoutTemplate,
} from '../../api';
import { ModuleDiscovery } from '../ModuleDiscovery';

type DiscoveryMode = 'nutrition' | 'exercise' | null;

const MEAL_LABELS: Record<'breakfast' | 'lunch' | 'dinner' | 'snack', string> = {
  breakfast: 'Desayuno',
  lunch: 'Almuerzo',
  dinner: 'Cena',
  snack: 'Snack',
};

const LEVEL_LABELS: Record<'minimum' | 'optimal', string> = {
  minimum: 'Minimo',
  optimal: 'Optimo',
};

function formatDateTime(ts: string): string {
  const d = new Date(ts.endsWith('Z') ? ts : `${ts}Z`);
  return d.toLocaleString('es-MX', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatDate(dateStr: string): string {
  const d = new Date(`${dateStr}T12:00:00`);
  return d.toLocaleDateString('es-MX', {
    month: 'short',
    day: 'numeric',
  });
}

function parseJsonList(raw: string | null | undefined): string[] {
  if (!raw) {
    return [];
  }
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed
      .map((item) => (typeof item === 'string' ? item.trim() : String(item)))
      .filter((item) => item.length > 0);
  } catch {
    return [];
  }
}

export function Cuerpo() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [savingFood, setSavingFood] = useState(false);
  const [savingSession, setSavingSession] = useState(false);

  const [nutritionProfile, setNutritionProfile] = useState<NutritionProfile | null>(null);
  const [nutritionTotals, setNutritionTotals] = useState<NutritionDailyTotals>({
    protein: 0,
    carbs: 0,
    fat: 0,
    calories: 0,
  });
  const [foodEntries, setFoodEntries] = useState<FoodEntry[]>([]);

  const [exerciseProfile, setExerciseProfile] = useState<ExerciseProfile | null>(null);
  const [templates, setTemplates] = useState<WorkoutTemplate[]>([]);
  const [sessions, setSessions] = useState<WorkoutSession[]>([]);

  const [discoveryMode, setDiscoveryMode] = useState<DiscoveryMode>(null);

  const [foodDescription, setFoodDescription] = useState('');
  const [foodMealType, setFoodMealType] = useState<'breakfast' | 'lunch' | 'dinner' | 'snack'>('snack');
  const [foodProtein, setFoodProtein] = useState('');
  const [foodCarbs, setFoodCarbs] = useState('');
  const [foodFat, setFoodFat] = useState('');
  const [foodCalories, setFoodCalories] = useState('');
  const [foodNotes, setFoodNotes] = useState('');
  const [foodError, setFoodError] = useState<string | null>(null);

  const [sessionLevel, setSessionLevel] = useState<'minimum' | 'optimal'>('minimum');
  const [sessionTemplateId, setSessionTemplateId] = useState('');
  const [sessionNotes, setSessionNotes] = useState('');
  const [sessionError, setSessionError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [
        nutritionProfileRes,
        nutritionEntriesRes,
        exerciseProfileRes,
        templatesRes,
        sessionsRes,
      ] = await Promise.all([
        fetchNutritionProfile(),
        fetchNutritionEntries({ today: true, limit: 50 }),
        fetchExerciseProfile(),
        fetchWorkoutTemplates(),
        fetchWorkoutSessions(20),
      ]);

      setNutritionProfile(nutritionProfileRes.profile || null);
      setNutritionTotals(nutritionProfileRes.daily_totals || { protein: 0, carbs: 0, fat: 0, calories: 0 });
      setFoodEntries(nutritionEntriesRes.entries || []);

      setExerciseProfile(exerciseProfileRes.profile || null);
      setTemplates(templatesRes.templates || []);
      setSessions(sessionsRes.sessions || []);
    } catch {
      setError('No se pudieron cargar los datos de Cuerpo.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const proteinTarget = nutritionProfile?.protein_target_g || 0;
  const proteinProgressPct = proteinTarget > 0
    ? Math.min(100, Math.round((nutritionTotals.protein / proteinTarget) * 100))
    : 0;

  const filteredTemplates = useMemo(
    () => templates.filter((template) => template.level === sessionLevel),
    [sessionLevel, templates],
  );

  const handleAddFood = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!foodDescription.trim()) {
      setFoodError('Describe que comiste para guardarlo.');
      return;
    }

    setSavingFood(true);
    setFoodError(null);

    const parseNumber = (value: string): number | null =>
      value.trim() === '' ? null : Number(value);

    const protein = parseNumber(foodProtein);
    const carbs = parseNumber(foodCarbs);
    const fat = parseNumber(foodFat);
    const calories = parseNumber(foodCalories);

    if (
      [protein, carbs, fat, calories].some(
        (value) => value != null && Number.isNaN(value),
      )
    ) {
      setSavingFood(false);
      setFoodError('Macros/calorias deben ser numeros validos.');
      return;
    }

    try {
      const res = await createNutritionEntry({
        description: foodDescription.trim(),
        meal_type: foodMealType,
        protein_g: protein,
        carbs_g: carbs,
        fat_g: fat,
        calories,
        notes: foodNotes.trim() || undefined,
      });

      if (!res.ok) {
        setFoodError(res.error || 'No se pudo guardar la comida.');
        return;
      }

      setFoodDescription('');
      setFoodMealType('snack');
      setFoodProtein('');
      setFoodCarbs('');
      setFoodFat('');
      setFoodCalories('');
      setFoodNotes('');
      await loadData();
    } catch {
      setFoodError('Error guardando comida.');
    } finally {
      setSavingFood(false);
    }
  };

  const handleAddSession = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingSession(true);
    setSessionError(null);

    const templateId = sessionTemplateId ? Number(sessionTemplateId) : undefined;
    if (templateId != null && Number.isNaN(templateId)) {
      setSavingSession(false);
      setSessionError('Plantilla invalida.');
      return;
    }

    const template = templateId ? templates.find((item) => item.id === templateId) : undefined;
    try {
      const res = await createWorkoutSession({
        level: sessionLevel,
        template_id: templateId,
        exercises: template?.exercises,
        notes: sessionNotes.trim() || undefined,
      });

      if (!res.ok) {
        setSessionError(res.error || 'No se pudo registrar la sesion.');
        return;
      }

      setSessionTemplateId('');
      setSessionNotes('');
      await loadData();
    } catch {
      setSessionError('Error guardando sesion.');
    } finally {
      setSavingSession(false);
    }
  };

  const nutritionRestrictions = parseJsonList(nutritionProfile?.restrictions_json);
  const nutritionSupplements = parseJsonList(nutritionProfile?.supplements_json);

  const exerciseGoals = parseJsonList(exerciseProfile?.goals_json);
  const exerciseLimitations = parseJsonList(exerciseProfile?.limitations_json);
  const exerciseEquipment = parseJsonList(exerciseProfile?.equipment_json);

  return (
    <>
      <div className="max-w-5xl mx-auto px-4 py-6 space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold text-[var(--nash-prussian)]">Cuerpo</h2>
            <p className="text-sm text-[var(--nash-text-muted)]">
              Nutricion y ejercicio en formato rapido, para iterar sin friccion.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => setDiscoveryMode('nutrition')}
              className="px-3 py-2 rounded-lg bg-[var(--nash-teal-soft)] text-[var(--nash-teal)] border border-[var(--nash-teal)] text-sm font-medium cursor-pointer hover:opacity-90"
            >
              Descubrir Nutricion
            </button>
            <button
              onClick={() => setDiscoveryMode('exercise')}
              className="px-3 py-2 rounded-lg bg-[var(--nash-prussian-soft)] text-[var(--nash-prussian)] border border-[var(--nash-prussian)] text-sm font-medium cursor-pointer hover:opacity-90"
            >
              Descubrir Ejercicio
            </button>
            <button
              onClick={loadData}
              className="px-3 py-2 rounded-lg border border-[var(--nash-border)] text-sm text-[var(--nash-text-muted)] cursor-pointer hover:text-[var(--nash-text)]"
            >
              Actualizar
            </button>
          </div>
        </div>

        {error && (
          <p className="text-sm text-[var(--nash-warning)]">{error}</p>
        )}

        {loading && (
          <p className="text-sm text-[var(--nash-text-muted)]">Cargando modulo...</p>
        )}

        {!loading && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <section className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded-xl p-5 space-y-5">
              <div>
                <h3 className="font-semibold text-[var(--nash-text)]">Nutricion</h3>
                <p className="text-xs text-[var(--nash-text-muted)]">
                  Registro diario + objetivo de proteina.
                </p>
              </div>

              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="bg-[var(--nash-surface-2)] rounded-lg p-3">
                  <p className="text-xs text-[var(--nash-text-muted)]">Peso actual</p>
                  <p className="font-semibold">{nutritionProfile?.weight_kg ?? '-'} kg</p>
                </div>
                <div className="bg-[var(--nash-surface-2)] rounded-lg p-3">
                  <p className="text-xs text-[var(--nash-text-muted)]">Peso objetivo</p>
                  <p className="font-semibold">{nutritionProfile?.goal_weight_kg ?? '-'} kg</p>
                </div>
              </div>

              <div className="bg-[var(--nash-surface-2)] rounded-lg p-3 space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span>Proteina hoy</span>
                  <span className="font-semibold">
                    {Math.round(nutritionTotals.protein)}g
                    {proteinTarget > 0 ? ` / ${Math.round(proteinTarget)}g` : ''}
                  </span>
                </div>
                {proteinTarget > 0 && (
                  <>
                    <div className="h-2 bg-[var(--nash-border)] rounded-full overflow-hidden">
                      <div
                        className="h-full bg-[var(--nash-teal)] transition-all"
                        style={{ width: `${proteinProgressPct}%` }}
                      />
                    </div>
                    <p className="text-xs text-[var(--nash-text-muted)]">{proteinProgressPct}% de la meta diaria</p>
                  </>
                )}
                <p className="text-xs text-[var(--nash-text-muted)]">
                  Carbs: {Math.round(nutritionTotals.carbs)}g · Grasa: {Math.round(nutritionTotals.fat)}g · Calorias: {Math.round(nutritionTotals.calories)}
                </p>
              </div>

              {(nutritionRestrictions.length > 0 || nutritionSupplements.length > 0) && (
                <div className="text-xs text-[var(--nash-text-muted)] space-y-1">
                  {nutritionRestrictions.length > 0 && (
                    <p>Restricciones: {nutritionRestrictions.join(', ')}</p>
                  )}
                  {nutritionSupplements.length > 0 && (
                    <p>Suplementos: {nutritionSupplements.join(', ')}</p>
                  )}
                </div>
              )}

              <form onSubmit={handleAddFood} className="space-y-2">
                <p className="text-sm font-medium">Agregar comida</p>
                <textarea
                  value={foodDescription}
                  onChange={(e) => setFoodDescription(e.target.value)}
                  placeholder="Ej: almuerzo: pollo con arroz y ensalada"
                  rows={2}
                  className="w-full bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                />

                <div className="grid grid-cols-2 gap-2">
                  <select
                    value={foodMealType}
                    onChange={(e) => setFoodMealType(e.target.value as 'breakfast' | 'lunch' | 'dinner' | 'snack')}
                    className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                  >
                    {Object.entries(MEAL_LABELS).map(([value, label]) => (
                      <option key={value} value={value}>{label}</option>
                    ))}
                  </select>
                  <input
                    value={foodCalories}
                    onChange={(e) => setFoodCalories(e.target.value)}
                    placeholder="Calorias (opc)"
                    className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                  />
                </div>

                <div className="grid grid-cols-3 gap-2">
                  <input
                    value={foodProtein}
                    onChange={(e) => setFoodProtein(e.target.value)}
                    placeholder="Proteina g"
                    className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                  />
                  <input
                    value={foodCarbs}
                    onChange={(e) => setFoodCarbs(e.target.value)}
                    placeholder="Carbs g"
                    className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                  />
                  <input
                    value={foodFat}
                    onChange={(e) => setFoodFat(e.target.value)}
                    placeholder="Grasa g"
                    className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                  />
                </div>

                <input
                  value={foodNotes}
                  onChange={(e) => setFoodNotes(e.target.value)}
                  placeholder="Notas (opcional)"
                  className="w-full bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                />

                {foodError && <p className="text-xs text-[var(--nash-warning)]">{foodError}</p>}

                <button
                  type="submit"
                  disabled={savingFood}
                  className="px-3 py-2 rounded-lg bg-[var(--nash-accent)] text-white text-sm font-medium hover:opacity-90 disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed"
                >
                  {savingFood ? 'Guardando...' : 'Guardar comida'}
                </button>
              </form>

              <div className="space-y-2">
                <p className="text-sm font-medium">Comidas de hoy ({foodEntries.length})</p>
                {foodEntries.length === 0 && (
                  <p className="text-xs text-[var(--nash-text-muted)]">Aun no registras comidas hoy.</p>
                )}
                {foodEntries.slice().reverse().map((entry) => (
                  <div key={entry.id} className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg p-3">
                    <div className="flex items-center justify-between text-xs text-[var(--nash-text-muted)]">
                      <span>{MEAL_LABELS[entry.meal_type] || entry.meal_type}</span>
                      <span>{formatDateTime(entry.timestamp)}</span>
                    </div>
                    <p className="text-sm mt-1">{entry.description}</p>
                    <p className="text-xs text-[var(--nash-text-muted)] mt-1">
                      P: {entry.protein_g ?? 0}g · C: {entry.carbs_g ?? 0}g · G: {entry.fat_g ?? 0}g · Kcal: {entry.calories ?? 0}
                      {entry.is_estimated ? ' · estimado' : ''}
                    </p>
                  </div>
                ))}
              </div>
            </section>

            <section className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded-xl p-5 space-y-5">
              <div>
                <h3 className="font-semibold text-[var(--nash-text)]">Ejercicio</h3>
                <p className="text-xs text-[var(--nash-text-muted)]">
                  Sistema minimo/optimo para mantener consistencia.
                </p>
              </div>

              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="bg-[var(--nash-surface-2)] rounded-lg p-3">
                  <p className="text-xs text-[var(--nash-text-muted)]">Nivel</p>
                  <p className="font-semibold">{exerciseProfile?.fitness_level || '-'}</p>
                </div>
                <div className="bg-[var(--nash-surface-2)] rounded-lg p-3">
                  <p className="text-xs text-[var(--nash-text-muted)]">Dias/semana</p>
                  <p className="font-semibold">{exerciseProfile?.workout_days_per_week ?? '-'}</p>
                </div>
                <div className="bg-[var(--nash-surface-2)] rounded-lg p-3">
                  <p className="text-xs text-[var(--nash-text-muted)]">Min por sesion</p>
                  <p className="font-semibold">{exerciseProfile?.time_per_workout_min ?? '-'} min</p>
                </div>
                <div className="bg-[var(--nash-surface-2)] rounded-lg p-3">
                  <p className="text-xs text-[var(--nash-text-muted)]">Gym</p>
                  <p className="font-semibold">
                    {exerciseProfile?.has_gym_access ? 'Activo' : 'No'}
                    {exerciseProfile?.gym_start_date ? ` (${exerciseProfile.gym_start_date})` : ''}
                  </p>
                </div>
              </div>

              {(exerciseGoals.length > 0 || exerciseLimitations.length > 0 || exerciseEquipment.length > 0) && (
                <div className="text-xs text-[var(--nash-text-muted)] space-y-1">
                  {exerciseGoals.length > 0 && <p>Metas: {exerciseGoals.join(', ')}</p>}
                  {exerciseEquipment.length > 0 && <p>Equipamiento: {exerciseEquipment.join(', ')}</p>}
                  {exerciseLimitations.length > 0 && <p>Limitaciones: {exerciseLimitations.join(', ')}</p>}
                </div>
              )}

              <form onSubmit={handleAddSession} className="space-y-2">
                <p className="text-sm font-medium">Registrar sesion</p>
                <div className="grid grid-cols-2 gap-2">
                  <select
                    value={sessionLevel}
                    onChange={(e) => {
                      setSessionLevel(e.target.value as 'minimum' | 'optimal');
                      setSessionTemplateId('');
                    }}
                    className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                  >
                    <option value="minimum">Minimo (10-15 min)</option>
                    <option value="optimal">Optimo (45-60 min)</option>
                  </select>
                  <select
                    value={sessionTemplateId}
                    onChange={(e) => setSessionTemplateId(e.target.value)}
                    className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                  >
                    <option value="">Sin plantilla</option>
                    {filteredTemplates.map((template) => (
                      <option key={template.id} value={template.id}>
                        {template.name}
                      </option>
                    ))}
                  </select>
                </div>

                <input
                  value={sessionNotes}
                  onChange={(e) => setSessionNotes(e.target.value)}
                  placeholder="Notas (energia, dolor, ajustes...)"
                  className="w-full bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                />

                {sessionError && <p className="text-xs text-[var(--nash-warning)]">{sessionError}</p>}

                <button
                  type="submit"
                  disabled={savingSession}
                  className="px-3 py-2 rounded-lg bg-[var(--nash-accent)] text-white text-sm font-medium hover:opacity-90 disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed"
                >
                  {savingSession ? 'Guardando...' : 'Guardar sesion'}
                </button>
              </form>

              <div className="space-y-2">
                <p className="text-sm font-medium">Sesiones recientes ({sessions.length})</p>
                {sessions.length === 0 && (
                  <p className="text-xs text-[var(--nash-text-muted)]">Aun no registras entrenamientos.</p>
                )}
                {sessions.map((session) => (
                  <div key={session.id} className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg p-3">
                    <div className="flex items-center justify-between text-xs text-[var(--nash-text-muted)]">
                      <span>{formatDate(session.date)}</span>
                      <span>{LEVEL_LABELS[session.level] || session.level}</span>
                    </div>
                    <p className="text-sm mt-1">
                      {session.template_name || 'Sesion libre'}
                    </p>
                    <p className="text-xs text-[var(--nash-text-muted)] mt-1">
                      {session.notes || 'Sin notas'}
                    </p>
                  </div>
                ))}
              </div>
            </section>
          </div>
        )}
      </div>

      {discoveryMode && (
        <ModuleDiscovery
          module={discoveryMode}
          title={discoveryMode === 'nutrition' ? 'Descubrimiento de Nutricion' : 'Descubrimiento de Ejercicio'}
          subtitle={
            discoveryMode === 'nutrition'
              ? 'Define metas de proteina, peso y habitos alimenticios.'
              : 'Configura nivel, equipamiento y rutina minimo/optimo.'
          }
          onClose={() => {
            setDiscoveryMode(null);
            loadData();
          }}
          onProfileUpdated={loadData}
        />
      )}
    </>
  );
}
