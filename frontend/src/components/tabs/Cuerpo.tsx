import { useCallback, useEffect, useState } from 'react';
import {
  createExerciseEquipment,
  createExerciseMeasurement,
  createNutritionEntry,
  createWorkoutSession,
  deleteExerciseEquipment,
  fetchExerciseDashboard,
  fetchNutritionEntries,
  fetchNutritionProfile,
  generateWorkoutPlan,
  updateExerciseProfile,
  type ExerciseDashboard,
  type ExerciseLogEntry,
  type ExerciseProfile,
  type FoodEntry,
  type NutritionDailyTotals,
  type NutritionProfile,
  type WorkoutPlan,
  type WorkoutPlanExercise,
  type WorkoutPlanSession,
} from '../../api';
import { ModuleDiscovery } from '../ModuleDiscovery';

type DiscoveryMode = 'nutrition' | 'exercise' | null;

type EditableSet = {
  reps: string;
  weight_kg: string;
  rir: string;
  rpe: string;
  reached_failure: boolean;
  completed: boolean;
};

type EditableExerciseLog = {
  exercise_name: string;
  movement_pattern: string;
  equipment_context: string;
  location: 'home' | 'gym';
  notes: string;
  rep_range: string;
  sets: EditableSet[];
};

const MEAL_LABELS: Record<'breakfast' | 'lunch' | 'dinner' | 'snack', string> = {
  breakfast: 'Desayuno',
  lunch: 'Almuerzo',
  dinner: 'Cena',
  snack: 'Snack',
};

const EQUIPMENT_CATEGORIES = [
  { value: 'dumbbells', label: 'Mancuernas' },
  { value: 'bands', label: 'Bandas' },
  { value: 'bench', label: 'Banca' },
  { value: 'barbell', label: 'Barra' },
  { value: 'rack', label: 'Rack/Jaula' },
  { value: 'smith', label: 'Smith machine' },
  { value: 'cable', label: 'Polea/Cable' },
  { value: 'machine_press', label: 'Maquina press' },
  { value: 'machine_pull', label: 'Maquina remo/pulldown' },
  { value: 'machine_lower', label: 'Maquina de piernas' },
  { value: 'pullup_bar', label: 'Barra de dominadas' },
  { value: 'kettlebell', label: 'Kettlebell' },
  { value: 'other', label: 'Otro' },
];

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
    year: 'numeric',
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

function listToCsv(items: string[]): string {
  return items.join(', ');
}

function csvToJson(raw: string): string {
  const values = raw
    .split(',')
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
  return JSON.stringify(values);
}

function parseNumber(value: string): number | null {
  if (!value.trim()) {
    return null;
  }
  const parsed = Number(value);
  return Number.isNaN(parsed) ? null : parsed;
}

function hasInvalidNumberInput(value: string): boolean {
  return value.trim().length > 0 && parseNumber(value) == null;
}

function rirSuggestion(label: string): string {
  if (label.includes('0-2')) {
    return '1';
  }
  if (label.includes('1-3')) {
    return '2';
  }
  return '';
}

function buildEditableLogsFromPlan(session: WorkoutPlanSession): EditableExerciseLog[] {
  return session.exercises.map((exercise) => ({
    exercise_name: exercise.name,
    movement_pattern: exercise.movement_pattern,
    equipment_context: exercise.equipment_context,
    location: session.location,
    notes: '',
    rep_range: exercise.rep_range,
    sets: Array.from({ length: exercise.sets }, () => ({
      reps: '',
      weight_kg: '',
      rir: rirSuggestion(exercise.rir_target),
      rpe: '',
      reached_failure: false,
      completed: false,
    })),
  }));
}

function summarizeSetHistory(exercise: WorkoutPlanExercise): string {
  const bestSet = exercise.last_performance?.best_set;
  if (!bestSet) {
    return 'Sin referencia previa';
  }
  if (!bestSet.weight_kg) {
    return `${bestSet.reps} reps`;
  }
  return `${bestSet.weight_kg} kg x ${bestSet.reps}`;
}

export function Cuerpo() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [savingFood, setSavingFood] = useState(false);
  const [savingProfile, setSavingProfile] = useState(false);
  const [savingEquipment, setSavingEquipment] = useState(false);
  const [savingMeasurement, setSavingMeasurement] = useState(false);
  const [savingSession, setSavingSession] = useState(false);
  const [generatingPlan, setGeneratingPlan] = useState(false);

  const [nutritionProfile, setNutritionProfile] = useState<NutritionProfile | null>(null);
  const [nutritionTotals, setNutritionTotals] = useState<NutritionDailyTotals>({
    protein: 0,
    carbs: 0,
    fat: 0,
    calories: 0,
  });
  const [foodEntries, setFoodEntries] = useState<FoodEntry[]>([]);

  const [dashboard, setDashboard] = useState<ExerciseDashboard | null>(null);
  const [exerciseProfile, setExerciseProfile] = useState<ExerciseProfile | null>(null);
  const [workoutPlan, setWorkoutPlan] = useState<WorkoutPlan | null>(null);
  const [activePlanMode, setActivePlanMode] = useState<'primary' | 'fallback'>('primary');

  const [discoveryMode, setDiscoveryMode] = useState<DiscoveryMode>(null);

  const [foodDescription, setFoodDescription] = useState('');
  const [foodMealType, setFoodMealType] = useState<'breakfast' | 'lunch' | 'dinner' | 'snack'>('snack');
  const [foodProtein, setFoodProtein] = useState('');
  const [foodCarbs, setFoodCarbs] = useState('');
  const [foodFat, setFoodFat] = useState('');
  const [foodCalories, setFoodCalories] = useState('');
  const [foodNotes, setFoodNotes] = useState('');
  const [foodError, setFoodError] = useState<string | null>(null);

  const [profileFitnessLevel, setProfileFitnessLevel] = useState<'beginner' | 'intermediate' | 'advanced'>('beginner');
  const [profilePrimaryGoal, setProfilePrimaryGoal] = useState<'muscle_gain' | 'strength' | 'recomposition' | 'general_fitness'>('muscle_gain');
  const [profileDays, setProfileDays] = useState('3');
  const [profileMinimumMin, setProfileMinimumMin] = useState('12');
  const [profileOptimalMin, setProfileOptimalMin] = useState('45');
  const [profileHeightCm, setProfileHeightCm] = useState('');
  const [profilePreferredLocation, setProfilePreferredLocation] = useState<'home' | 'gym' | 'either'>('either');
  const [profileHasGym, setProfileHasGym] = useState(false);
  const [profileGymStartDate, setProfileGymStartDate] = useState('');
  const [profileScheduleDays, setProfileScheduleDays] = useState('');
  const [profileBarriers, setProfileBarriers] = useState('');
  const [profileEnjoyment, setProfileEnjoyment] = useState('');
  const [profileNotes, setProfileNotes] = useState('');
  const [profileTrainingHistory, setProfileTrainingHistory] = useState('');
  const [profileError, setProfileError] = useState<string | null>(null);

  const [equipmentLocation, setEquipmentLocation] = useState<'home' | 'gym'>('home');
  const [equipmentCategory, setEquipmentCategory] = useState('dumbbells');
  const [equipmentLabel, setEquipmentLabel] = useState('');
  const [equipmentMaxLoad, setEquipmentMaxLoad] = useState('');
  const [equipmentQuantity, setEquipmentQuantity] = useState('1');
  const [equipmentNotes, setEquipmentNotes] = useState('');
  const [equipmentError, setEquipmentError] = useState<string | null>(null);

  const [measurementTakenOn, setMeasurementTakenOn] = useState(new Date().toISOString().slice(0, 10));
  const [measurementWeightKg, setMeasurementWeightKg] = useState('');
  const [measurementWaistCm, setMeasurementWaistCm] = useState('');
  const [measurementHipCm, setMeasurementHipCm] = useState('');
  const [measurementChestCm, setMeasurementChestCm] = useState('');
  const [measurementArmRelaxedCm, setMeasurementArmRelaxedCm] = useState('');
  const [measurementArmFlexedCm, setMeasurementArmFlexedCm] = useState('');
  const [measurementThighCm, setMeasurementThighCm] = useState('');
  const [measurementCalfCm, setMeasurementCalfCm] = useState('');
  const [measurementNotes, setMeasurementNotes] = useState('');
  const [measurementError, setMeasurementError] = useState<string | null>(null);

  const [planLocation, setPlanLocation] = useState<'home' | 'gym'>('home');
  const [planEnergy, setPlanEnergy] = useState('6');
  const [planTimeMin, setPlanTimeMin] = useState('45');
  const [planDesiredMode, setPlanDesiredMode] = useState<'auto' | 'minimum' | 'optimal'>('auto');

  const [sessionDate, setSessionDate] = useState(new Date().toISOString().slice(0, 10));
  const [sessionLevel, setSessionLevel] = useState<'minimum' | 'optimal'>('minimum');
  const [sessionLocation, setSessionLocation] = useState<'home' | 'gym'>('home');
  const [sessionFocusCode, setSessionFocusCode] = useState('');
  const [sessionDurationMin, setSessionDurationMin] = useState('15');
  const [sessionEnergy, setSessionEnergy] = useState('6');
  const [sessionRpe, setSessionRpe] = useState('7');
  const [sessionNotes, setSessionNotes] = useState('');
  const [sessionFallbackUsed, setSessionFallbackUsed] = useState(false);
  const [sessionError, setSessionError] = useState<string | null>(null);
  const [sessionLogs, setSessionLogs] = useState<EditableExerciseLog[]>([]);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [nutritionProfileRes, nutritionEntriesRes, dashboardRes] = await Promise.all([
        fetchNutritionProfile(),
        fetchNutritionEntries({ today: true, limit: 50 }),
        fetchExerciseDashboard(),
      ]);

      setNutritionProfile(nutritionProfileRes.profile || null);
      setNutritionTotals(
        nutritionProfileRes.daily_totals || { protein: 0, carbs: 0, fat: 0, calories: 0 },
      );
      setFoodEntries(nutritionEntriesRes.entries || []);

      setDashboard(dashboardRes);
      setExerciseProfile(dashboardRes.profile || null);
      setWorkoutPlan(dashboardRes.today_plan || null);
      setActivePlanMode('primary');
    } catch {
      setError('No se pudieron cargar los datos de Cuerpo.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  useEffect(() => {
    if (!exerciseProfile) {
      return;
    }
    setProfileFitnessLevel(exerciseProfile.fitness_level || 'beginner');
    setProfilePrimaryGoal(exerciseProfile.primary_goal || 'muscle_gain');
    setProfileDays(String(exerciseProfile.workout_days_per_week ?? 3));
    setProfileMinimumMin(String(exerciseProfile.minimum_session_min ?? 12));
    setProfileOptimalMin(
      String(exerciseProfile.optimal_session_min ?? exerciseProfile.time_per_workout_min ?? 45),
    );
    setProfileHeightCm(exerciseProfile.height_cm != null ? String(exerciseProfile.height_cm) : '');
    setProfilePreferredLocation(exerciseProfile.preferred_location || 'either');
    setProfileHasGym(Boolean(exerciseProfile.has_gym_access));
    setProfileGymStartDate(exerciseProfile.gym_start_date || '');
    setProfileScheduleDays(listToCsv(exerciseProfile.schedule_days || parseJsonList(exerciseProfile.schedule_days_json)));
    setProfileBarriers(listToCsv(exerciseProfile.barriers || parseJsonList(exerciseProfile.barriers_json)));
    setProfileEnjoyment(listToCsv(exerciseProfile.enjoyment || parseJsonList(exerciseProfile.enjoyment_json)));
    setProfileNotes(exerciseProfile.notes || '');
    setProfileTrainingHistory(exerciseProfile.training_history_notes || '');
  }, [exerciseProfile]);

  useEffect(() => {
    if (!workoutPlan) {
      return;
    }
    const session = activePlanMode === 'fallback' ? workoutPlan.fallback_session : workoutPlan.primary_session;
    setPlanLocation(workoutPlan.input.location);
    setPlanEnergy(String(workoutPlan.input.energy_level));
    setPlanTimeMin(String(workoutPlan.input.available_time_min));
    setSessionLevel(session.level);
    setSessionLocation(session.location);
    setSessionFocusCode(session.focus_code);
    setSessionDurationMin(String(session.estimated_duration_min));
    setSessionFallbackUsed(activePlanMode === 'fallback');
    setSessionLogs(buildEditableLogsFromPlan(session));
  }, [activePlanMode, workoutPlan]);

  const proteinTarget = nutritionProfile?.protein_target_g || 0;
  const proteinProgressPct = proteinTarget > 0
    ? Math.min(100, Math.round((nutritionTotals.protein / proteinTarget) * 100))
    : 0;

  const handleAddFood = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!foodDescription.trim()) {
      setFoodError('Describe que comiste para guardarlo.');
      return;
    }

    setSavingFood(true);
    setFoodError(null);

    const protein = parseNumber(foodProtein);
    const carbs = parseNumber(foodCarbs);
    const fat = parseNumber(foodFat);
    const calories = parseNumber(foodCalories);

    if ([foodProtein, foodCarbs, foodFat, foodCalories].some(hasInvalidNumberInput)) {
      setSavingFood(false);
      setFoodError('Macros y calorias deben ser numeros validos.');
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

  const handleSaveExerciseProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if ([profileDays, profileMinimumMin, profileOptimalMin, profileHeightCm].some(hasInvalidNumberInput)) {
      setProfileError('Dias, minutos y altura deben ser numeros validos.');
      return;
    }
    setSavingProfile(true);
    setProfileError(null);
    try {
      const payload = {
        fitness_level: profileFitnessLevel,
        primary_goal: profilePrimaryGoal,
        workout_days_per_week: parseNumber(profileDays),
        minimum_session_min: parseNumber(profileMinimumMin),
        optimal_session_min: parseNumber(profileOptimalMin),
        time_per_workout_min: parseNumber(profileOptimalMin),
        height_cm: parseNumber(profileHeightCm),
        preferred_location: profilePreferredLocation,
        has_gym_access: profileHasGym ? 1 : 0,
        gym_start_date: profileGymStartDate || null,
        schedule_days_json: csvToJson(profileScheduleDays),
        barriers_json: csvToJson(profileBarriers),
        enjoyment_json: csvToJson(profileEnjoyment),
        notes: profileNotes.trim() || null,
        training_history_notes: profileTrainingHistory.trim() || null,
      };
      const res = await updateExerciseProfile(payload);
      if (!res.ok) {
        setProfileError('No se pudo guardar el perfil.');
        return;
      }
      await loadData();
    } catch {
      setProfileError('Error guardando perfil de entrenamiento.');
    } finally {
      setSavingProfile(false);
    }
  };

  const handleAddEquipment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!equipmentLabel.trim()) {
      setEquipmentError('Ponle un nombre al equipo.');
      return;
    }
    if ([equipmentMaxLoad, equipmentQuantity].some(hasInvalidNumberInput)) {
      setEquipmentError('Carga maxima y cantidad deben ser numeros validos.');
      return;
    }
    setSavingEquipment(true);
    setEquipmentError(null);
    try {
      const res = await createExerciseEquipment({
        location: equipmentLocation,
        category: equipmentCategory,
        label: equipmentLabel.trim(),
        max_load_kg: parseNumber(equipmentMaxLoad) ?? undefined,
        quantity: parseNumber(equipmentQuantity) ?? undefined,
        notes: equipmentNotes.trim() || undefined,
      });
      if (!res.ok) {
        setEquipmentError(res.error || 'No se pudo guardar el equipo.');
        return;
      }
      setEquipmentLabel('');
      setEquipmentMaxLoad('');
      setEquipmentQuantity('1');
      setEquipmentNotes('');
      await loadData();
    } catch {
      setEquipmentError('Error guardando equipo.');
    } finally {
      setSavingEquipment(false);
    }
  };

  const handleDeleteEquipment = async (id: number) => {
    await deleteExerciseEquipment(id);
    await loadData();
  };

  const handleAddMeasurement = async (e: React.FormEvent) => {
    e.preventDefault();
    const measurementInputs = [
      measurementWeightKg,
      measurementWaistCm,
      measurementHipCm,
      measurementChestCm,
      measurementArmRelaxedCm,
      measurementArmFlexedCm,
      measurementThighCm,
      measurementCalfCm,
    ];
    if (!measurementInputs.some((value) => value.trim().length > 0)) {
      setMeasurementError('Guarda al menos una medida corporal.');
      return;
    }
    if (measurementInputs.some(hasInvalidNumberInput)) {
      setMeasurementError('Las mediciones deben ser numeros validos.');
      return;
    }
    setSavingMeasurement(true);
    setMeasurementError(null);
    try {
      const res = await createExerciseMeasurement({
        taken_on: measurementTakenOn,
        weight_kg: parseNumber(measurementWeightKg),
        waist_cm: parseNumber(measurementWaistCm),
        hip_cm: parseNumber(measurementHipCm),
        chest_cm: parseNumber(measurementChestCm),
        arm_relaxed_cm: parseNumber(measurementArmRelaxedCm),
        arm_flexed_cm: parseNumber(measurementArmFlexedCm),
        thigh_cm: parseNumber(measurementThighCm),
        calf_cm: parseNumber(measurementCalfCm),
        notes: measurementNotes.trim() || null,
      });
      if (!res.ok) {
        setMeasurementError('No se pudo guardar la medicion.');
        return;
      }
      setMeasurementNotes('');
      await loadData();
    } catch {
      setMeasurementError('Error guardando medicion.');
    } finally {
      setSavingMeasurement(false);
    }
  };

  const handleGeneratePlan = async (e: React.FormEvent) => {
    e.preventDefault();
    if ([planEnergy, planTimeMin].some(hasInvalidNumberInput)) {
      setSessionError('Energia y minutos disponibles deben ser numeros validos.');
      return;
    }
    setGeneratingPlan(true);
    setSessionError(null);
    try {
      const res = await generateWorkoutPlan({
        location: planLocation,
        energy_level: parseNumber(planEnergy) ?? 6,
        available_time_min: parseNumber(planTimeMin) ?? 45,
        desired_mode: planDesiredMode,
      });
      setWorkoutPlan(res.plan);
      setActivePlanMode('primary');
    } catch {
      setSessionError('No se pudo generar el plan de hoy.');
    } finally {
      setGeneratingPlan(false);
    }
  };

  const loadPlanIntoLogger = (mode: 'primary' | 'fallback') => {
    setActivePlanMode(mode);
    setSessionNotes(mode === 'fallback' ? 'Use la version de rescate en casa.' : '');
  };

  const handleUpdateSet = (
    exerciseIndex: number,
    setIndex: number,
    field: keyof EditableSet,
    value: string | boolean,
  ) => {
    setSessionLogs((current) => current.map((exercise, exIdx) => {
      if (exIdx !== exerciseIndex) {
        return exercise;
      }
      return {
        ...exercise,
        sets: exercise.sets.map((setItem, sIdx) => {
          if (sIdx !== setIndex) {
            return setItem;
          }
          return { ...setItem, [field]: value };
        }),
      };
    }));
  };

  const handleUpdateExerciseNote = (exerciseIndex: number, notes: string) => {
    setSessionLogs((current) => current.map((exercise, exIdx) => (
      exIdx === exerciseIndex ? { ...exercise, notes } : exercise
    )));
  };

  const handleAddCustomExercise = () => {
    setSessionLogs((current) => [
      ...current,
      {
        exercise_name: '',
        movement_pattern: 'custom',
        equipment_context: 'libre',
        location: sessionLocation,
        notes: '',
        rep_range: '8-12',
        sets: [{
          reps: '',
          weight_kg: '',
          rir: '2',
          rpe: '',
          reached_failure: false,
          completed: false,
        }],
      },
    ]);
  };

  const handleUpdateExerciseName = (exerciseIndex: number, name: string) => {
    setSessionLogs((current) => current.map((exercise, exIdx) => (
      exIdx === exerciseIndex ? { ...exercise, exercise_name: name } : exercise
    )));
  };

  const handleSaveSession = async (e: React.FormEvent) => {
    e.preventDefault();
    if ([sessionDurationMin, sessionEnergy, sessionRpe].some(hasInvalidNumberInput)) {
      setSessionError('Duracion, energia y RPE deben ser numeros validos.');
      return;
    }
    setSavingSession(true);
    setSessionError(null);
    try {
      const logs: ExerciseLogEntry[] = sessionLogs
        .map((exercise) => ({
          exercise_name: exercise.exercise_name.trim(),
          movement_pattern: exercise.movement_pattern,
          equipment_context: exercise.equipment_context,
          location: sessionLocation,
          notes: exercise.notes.trim() || undefined,
          sets: exercise.sets
            .map((setItem) => {
              const reps = parseNumber(setItem.reps);
              const weightKg = parseNumber(setItem.weight_kg);
              const rir = parseNumber(setItem.rir);
              const rpe = parseNumber(setItem.rpe);
              const completed = Boolean(setItem.completed || reps != null || weightKg != null);
              if (!completed) {
                return null;
              }
              return {
                reps,
                weight_kg: weightKg ?? 0,
                rir,
                rpe,
                reached_failure: setItem.reached_failure,
                completed,
              };
            })
            .filter(Boolean) as ExerciseLogEntry['sets'],
        }))
        .filter((exercise) => exercise.exercise_name.length > 0 && exercise.sets.length > 0);

      if (logs.length === 0) {
        setSessionError('Registra al menos un ejercicio con una serie hecha.');
        return;
      }

      const res = await createWorkoutSession({
        date: sessionDate,
        level: sessionLevel,
        focus_code: sessionFocusCode || undefined,
        planned_location: sessionLocation,
        actual_location: sessionLocation,
        duration_min: parseNumber(sessionDurationMin) ?? undefined,
        notes: sessionNotes.trim() || undefined,
        energy_level: parseNumber(sessionEnergy) ?? undefined,
        session_rpe: parseNumber(sessionRpe) ?? undefined,
        fallback_used: sessionFallbackUsed,
        plan_source: 'generated',
        completed: 1,
        exercise_logs: logs,
      });
      if (!res.ok) {
        setSessionError(res.error || 'No se pudo guardar el entrenamiento.');
        return;
      }
      setSessionNotes('');
      await loadData();
    } catch {
      setSessionError('Error guardando entrenamiento.');
    } finally {
      setSavingSession(false);
    }
  };

  const nutritionRestrictions = parseJsonList(nutritionProfile?.restrictions_json);
  const nutritionSupplements = parseJsonList(nutritionProfile?.supplements_json);

  const equipmentHome = dashboard?.equipment.filter((item) => item.location === 'home') || [];
  const equipmentGym = dashboard?.equipment.filter((item) => item.location === 'gym') || [];
  const latestMeasurement = dashboard?.latest_measurement || null;
  const currentPlanSession = workoutPlan
    ? (activePlanMode === 'fallback' ? workoutPlan.fallback_session : workoutPlan.primary_session)
    : null;

  return (
    <>
      <div className="max-w-6xl mx-auto px-4 py-6 space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold text-[var(--nash-prussian)]">Cuerpo</h2>
            <p className="text-sm text-[var(--nash-text-muted)]">
              Motor de entrenamiento realista para ganar musculo sin depender de motivacion perfecta.
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

        {error && <p className="text-sm text-[var(--nash-warning)]">{error}</p>}
        {loading && <p className="text-sm text-[var(--nash-text-muted)]">Cargando modulo...</p>}

        {!loading && (
          <>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <section className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded-xl p-5 space-y-5">
                <div>
                  <h3 className="font-semibold text-[var(--nash-text)]">Nutricion</h3>
                  <p className="text-xs text-[var(--nash-text-muted)]">
                    Proteina y comida del dia para que el entrenamiento tenga con que crecer.
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div className="bg-[var(--nash-surface-2)] rounded-lg p-3">
                    <p className="text-xs text-[var(--nash-text-muted)]">Peso actual</p>
                    <p className="font-semibold">{nutritionProfile?.weight_kg ?? '-'} kg</p>
                  </div>
                  <div className="bg-[var(--nash-surface-2)] rounded-lg p-3">
                    <p className="text-xs text-[var(--nash-text-muted)]">Meta proteina</p>
                    <p className="font-semibold">{proteinTarget ? `${proteinTarget} g` : '-'}</p>
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
                      <p className="text-xs text-[var(--nash-text-muted)]">
                        {proteinProgressPct}% de la meta diaria
                      </p>
                    </>
                  )}
                  <p className="text-xs text-[var(--nash-text-muted)]">
                    Carbs: {Math.round(nutritionTotals.carbs)}g · Grasa: {Math.round(nutritionTotals.fat)}g · Calorias: {Math.round(nutritionTotals.calories)}
                  </p>
                </div>

                {(nutritionRestrictions.length > 0 || nutritionSupplements.length > 0) && (
                  <div className="text-xs text-[var(--nash-text-muted)] space-y-1">
                    {nutritionRestrictions.length > 0 && <p>Restricciones: {nutritionRestrictions.join(', ')}</p>}
                    {nutritionSupplements.length > 0 && <p>Suplementos: {nutritionSupplements.join(', ')}</p>}
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
                  <h3 className="font-semibold text-[var(--nash-text)]">Motor de entrenamiento</h3>
                  <p className="text-xs text-[var(--nash-text-muted)]">
                    Enfoque minimo/optimo, adaptado a energia, equipo y consistencia.
                  </p>
                </div>

                <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 text-sm">
                  <div className="bg-[var(--nash-surface-2)] rounded-lg p-3">
                    <p className="text-xs text-[var(--nash-text-muted)]">Meta principal</p>
                    <p className="font-semibold">{exerciseProfile?.primary_goal || 'muscle_gain'}</p>
                  </div>
                  <div className="bg-[var(--nash-surface-2)] rounded-lg p-3">
                    <p className="text-xs text-[var(--nash-text-muted)]">Dias/semana</p>
                    <p className="font-semibold">{exerciseProfile?.workout_days_per_week ?? 3}</p>
                  </div>
                  <div className="bg-[var(--nash-surface-2)] rounded-lg p-3">
                    <p className="text-xs text-[var(--nash-text-muted)]">Minimo util</p>
                    <p className="font-semibold">{exerciseProfile?.minimum_session_min ?? 12} min</p>
                  </div>
                  <div className="bg-[var(--nash-surface-2)] rounded-lg p-3">
                    <p className="text-xs text-[var(--nash-text-muted)]">Ultimos 7 dias</p>
                    <p className="font-semibold">{String(dashboard?.adherence_7?.total_sessions ?? 0)} sesiones</p>
                  </div>
                </div>

                <div className="bg-[var(--nash-surface-2)] rounded-lg p-3 text-sm space-y-1">
                  <p className="font-medium">Lo que el motor esta optimizando</p>
                  <p className="text-[var(--nash-text-muted)]">
                    1. Sostener el habito con un piso bajo.
                  </p>
                  <p className="text-[var(--nash-text-muted)]">
                    2. Subir volumen solo cuando la adherencia ya existe.
                  </p>
                  <p className="text-[var(--nash-text-muted)]">
                    3. Usar el plan de casa si el gym no pasa ese dia.
                  </p>
                </div>

                <form onSubmit={handleSaveExerciseProfile} className="space-y-3">
                  <p className="text-sm font-medium">Configuracion de entrenamiento</p>
                  <div className="grid grid-cols-2 gap-2">
                    <select
                      value={profileFitnessLevel}
                      onChange={(e) => setProfileFitnessLevel(e.target.value as 'beginner' | 'intermediate' | 'advanced')}
                      className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                    >
                      <option value="beginner">Principiante</option>
                      <option value="intermediate">Intermedio</option>
                      <option value="advanced">Avanzado</option>
                    </select>
                    <select
                      value={profilePrimaryGoal}
                      onChange={(e) => setProfilePrimaryGoal(e.target.value as 'muscle_gain' | 'strength' | 'recomposition' | 'general_fitness')}
                      className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                    >
                      <option value="muscle_gain">Ganar musculo</option>
                      <option value="strength">Fuerza</option>
                      <option value="recomposition">Recomposicion</option>
                      <option value="general_fitness">General</option>
                    </select>
                  </div>

                  <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
                    <input
                      value={profileDays}
                      onChange={(e) => setProfileDays(e.target.value)}
                      placeholder="Dias/semana"
                      className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                    />
                    <input
                      value={profileMinimumMin}
                      onChange={(e) => setProfileMinimumMin(e.target.value)}
                      placeholder="Minimo min"
                      className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                    />
                    <input
                      value={profileOptimalMin}
                      onChange={(e) => setProfileOptimalMin(e.target.value)}
                      placeholder="Optimo min"
                      className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                    />
                    <input
                      value={profileHeightCm}
                      onChange={(e) => setProfileHeightCm(e.target.value)}
                      placeholder="Altura cm"
                      className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <select
                      value={profilePreferredLocation}
                      onChange={(e) => setProfilePreferredLocation(e.target.value as 'home' | 'gym' | 'either')}
                      className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                    >
                      <option value="either">Lugar flexible</option>
                      <option value="home">Casa</option>
                      <option value="gym">Gym</option>
                    </select>
                    <input
                      value={profileGymStartDate}
                      onChange={(e) => setProfileGymStartDate(e.target.value)}
                      type="date"
                      className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                    />
                  </div>

                  <label className="flex items-center gap-2 text-sm text-[var(--nash-text-muted)]">
                    <input
                      type="checkbox"
                      checked={profileHasGym}
                      onChange={(e) => setProfileHasGym(e.target.checked)}
                    />
                    Ya tienes acceso a gym
                  </label>

                  <input
                    value={profileScheduleDays}
                    onChange={(e) => setProfileScheduleDays(e.target.value)}
                    placeholder="Dias ideales (ej: lunes, miercoles, viernes)"
                    className="w-full bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                  />
                  <input
                    value={profileBarriers}
                    onChange={(e) => setProfileBarriers(e.target.value)}
                    placeholder="Barreras (ej: pereza, ansiedad, trabajo tarde)"
                    className="w-full bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                  />
                  <input
                    value={profileEnjoyment}
                    onChange={(e) => setProfileEnjoyment(e.target.value)}
                    placeholder="Lo que si disfrutas (ej: presses, espalda, sesiones cortas)"
                    className="w-full bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                  />
                  <textarea
                    value={profileTrainingHistory}
                    onChange={(e) => setProfileTrainingHistory(e.target.value)}
                    rows={2}
                    placeholder="Historia de entrenamiento: que te ha servido y que no"
                    className="w-full bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                  />
                  <textarea
                    value={profileNotes}
                    onChange={(e) => setProfileNotes(e.target.value)}
                    rows={2}
                    placeholder="Notas generales"
                    className="w-full bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                  />
                  {profileError && <p className="text-xs text-[var(--nash-warning)]">{profileError}</p>}
                  <button
                    type="submit"
                    disabled={savingProfile}
                    className="px-3 py-2 rounded-lg bg-[var(--nash-prussian)] text-white text-sm font-medium hover:opacity-90 disabled:opacity-50 cursor-pointer"
                  >
                    {savingProfile ? 'Guardando...' : 'Guardar configuracion'}
                  </button>
                </form>
              </section>
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-[1.1fr_0.9fr] gap-6">
              <section className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded-xl p-5 space-y-5">
                <div>
                  <h3 className="font-semibold text-[var(--nash-text)]">Plan de hoy</h3>
                  <p className="text-xs text-[var(--nash-text-muted)]">
                    Genera una sesion principal y una ruta de rescate si el gym no pasa.
                  </p>
                </div>

                <form onSubmit={handleGeneratePlan} className="grid grid-cols-2 lg:grid-cols-4 gap-2">
                  <select
                    value={planLocation}
                    onChange={(e) => setPlanLocation(e.target.value as 'home' | 'gym')}
                    className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                  >
                    <option value="home">Casa</option>
                    <option value="gym">Gym</option>
                  </select>
                  <input
                    value={planEnergy}
                    onChange={(e) => setPlanEnergy(e.target.value)}
                    placeholder="Energia 1-10"
                    className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                  />
                  <input
                    value={planTimeMin}
                    onChange={(e) => setPlanTimeMin(e.target.value)}
                    placeholder="Min disponibles"
                    className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                  />
                  <select
                    value={planDesiredMode}
                    onChange={(e) => setPlanDesiredMode(e.target.value as 'auto' | 'minimum' | 'optimal')}
                    className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                  >
                    <option value="auto">Modo auto</option>
                    <option value="minimum">Minimo</option>
                    <option value="optimal">Optimo</option>
                  </select>
                  <button
                    type="submit"
                    disabled={generatingPlan}
                    className="col-span-2 lg:col-span-4 px-3 py-2 rounded-lg bg-[var(--nash-accent)] text-white text-sm font-medium hover:opacity-90 disabled:opacity-50 cursor-pointer"
                  >
                    {generatingPlan ? 'Generando...' : 'Generar plan'}
                  </button>
                </form>

                {workoutPlan && (
                  <>
                    <div className="bg-[var(--nash-surface-2)] rounded-lg p-4 space-y-2 text-sm">
                      <p className="font-medium">
                        Fase actual: {workoutPlan.training_target.phase === 'foundation' ? 'Base' : 'Build'}
                      </p>
                      <p className="text-[var(--nash-text-muted)]">
                        Objetivo semanal: {workoutPlan.training_target.weekly_sessions_target} sesiones · {workoutPlan.training_target.hard_sets_goal_per_muscle} hard sets por grupo muscular.
                      </p>
                      {workoutPlan.notes.map((note) => (
                        <p key={note} className="text-[var(--nash-text-muted)]">{note}</p>
                      ))}
                    </div>

                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                      {[workoutPlan.primary_session, workoutPlan.fallback_session].map((session, idx) => {
                        const isFallback = idx === 1;
                        return (
                          <div key={session.name} className={`rounded-xl border p-4 space-y-3 ${isFallback ? 'border-[var(--nash-teal)] bg-[var(--nash-teal-soft)]/30' : 'border-[var(--nash-border)] bg-[var(--nash-bg)]'}`}>
                            <div className="flex items-center justify-between gap-3">
                              <div>
                                <p className="font-semibold text-sm">{session.name}</p>
                                <p className="text-xs text-[var(--nash-text-muted)]">
                                  {session.level === 'optimal' ? 'Optimo' : 'Minimo'} · {session.location} · {session.estimated_duration_min} min
                                </p>
                              </div>
                              <button
                                onClick={() => loadPlanIntoLogger(isFallback ? 'fallback' : 'primary')}
                                className="px-3 py-1.5 rounded-lg border border-[var(--nash-border)] text-xs cursor-pointer hover:bg-white"
                              >
                                Usar en registro
                              </button>
                            </div>
                            <p className="text-sm">{session.goal}</p>
                            <div className="space-y-2">
                              <p className="text-xs uppercase tracking-wide text-[var(--nash-text-muted)]">Calentamiento</p>
                              {session.warmup.map((item) => (
                                <p key={item} className="text-sm text-[var(--nash-text-muted)]">{item}</p>
                              ))}
                            </div>
                            <div className="space-y-3">
                              {session.exercises.map((exercise) => (
                                <div key={`${session.name}-${exercise.name}`} className="rounded-lg border border-[var(--nash-border)] bg-white/70 p-3">
                                  <div className="flex items-center justify-between gap-3">
                                    <p className="font-medium text-sm">{exercise.name}</p>
                                    <p className="text-xs text-[var(--nash-text-muted)]">
                                      {exercise.sets} x {exercise.rep_range}
                                    </p>
                                  </div>
                                  <p className="text-xs text-[var(--nash-text-muted)] mt-1">
                                    {exercise.equipment_context} · Descanso {exercise.rest_sec}s · {exercise.rir_target}
                                  </p>
                                  <p className="text-xs mt-2">{exercise.coaching}</p>
                                  <p className="text-xs text-[var(--nash-text-muted)] mt-1">
                                    Referencia previa: {summarizeSetHistory(exercise)}
                                  </p>
                                  <p className="text-xs text-[var(--nash-text-muted)] mt-1">{exercise.progression_tip}</p>
                                  <p className="text-xs text-[var(--nash-text-muted)] mt-1">{exercise.failure_guidance}</p>
                                </div>
                              ))}
                            </div>
                          </div>
                        );
                      })}
                    </div>

                    <div className="bg-[var(--nash-surface-2)] rounded-lg p-4 space-y-2">
                      <p className="text-sm font-medium">Semana sugerida</p>
                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-sm">
                        {workoutPlan.weekly_outline.map((item) => (
                          <div key={`${item.day}-${item.focus_code}`} className="rounded-lg border border-[var(--nash-border)] bg-[var(--nash-bg)] p-3">
                            <p className="font-medium">{item.day}</p>
                            <p className="text-xs text-[var(--nash-text-muted)]">{item.session} · {item.location} · {item.focus_code}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  </>
                )}
              </section>

              <section className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded-xl p-5 space-y-5">
                <div>
                  <h3 className="font-semibold text-[var(--nash-text)]">Registrar entrenamiento</h3>
                  <p className="text-xs text-[var(--nash-text-muted)]">
                    Guarda reps, peso, RIR y fallo para que Nash entienda progreso real y fatiga.
                  </p>
                </div>

                <form onSubmit={handleSaveSession} className="space-y-4">
                  <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
                    <input
                      type="date"
                      value={sessionDate}
                      onChange={(e) => setSessionDate(e.target.value)}
                      className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                    />
                    <select
                      value={sessionLevel}
                      onChange={(e) => setSessionLevel(e.target.value as 'minimum' | 'optimal')}
                      className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                    >
                      <option value="minimum">Minimo</option>
                      <option value="optimal">Optimo</option>
                    </select>
                    <select
                      value={sessionLocation}
                      onChange={(e) => setSessionLocation(e.target.value as 'home' | 'gym')}
                      className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                    >
                      <option value="home">Casa</option>
                      <option value="gym">Gym</option>
                    </select>
                    <input
                      value={sessionFocusCode}
                      onChange={(e) => setSessionFocusCode(e.target.value)}
                      placeholder="Foco (A/B/etc)"
                      className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                    />
                    <input
                      value={sessionDurationMin}
                      onChange={(e) => setSessionDurationMin(e.target.value)}
                      placeholder="Duracion min"
                      className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                    />
                    <input
                      value={sessionEnergy}
                      onChange={(e) => setSessionEnergy(e.target.value)}
                      placeholder="Energia 1-10"
                      className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                    />
                    <input
                      value={sessionRpe}
                      onChange={(e) => setSessionRpe(e.target.value)}
                      placeholder="RPE sesion"
                      className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                    />
                    <label className="flex items-center gap-2 rounded-lg border border-[var(--nash-border)] px-3 py-2 text-sm text-[var(--nash-text-muted)]">
                      <input
                        type="checkbox"
                        checked={sessionFallbackUsed}
                        onChange={(e) => setSessionFallbackUsed(e.target.checked)}
                      />
                      Fue plan rescate
                    </label>
                  </div>

                  {currentPlanSession && (
                    <p className="text-xs text-[var(--nash-text-muted)]">
                      Registro actual cargado desde: {currentPlanSession.name}
                    </p>
                  )}

                  <div className="space-y-3">
                    {sessionLogs.map((exercise, exerciseIndex) => (
                      <div key={`${exercise.exercise_name || 'custom'}-${exerciseIndex}`} className="rounded-xl border border-[var(--nash-border)] bg-[var(--nash-bg)] p-4 space-y-3">
                        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                          <input
                            value={exercise.exercise_name}
                            onChange={(e) => handleUpdateExerciseName(exerciseIndex, e.target.value)}
                            placeholder="Nombre del ejercicio"
                            className="w-full sm:max-w-xs bg-white border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                          />
                          <p className="text-xs text-[var(--nash-text-muted)]">
                            {exercise.equipment_context} · rango {exercise.rep_range}
                          </p>
                        </div>
                        <div className="space-y-2">
                          {exercise.sets.map((setItem, setIndex) => (
                            <div key={`${exercise.exercise_name || 'custom'}-set-${setIndex}`} className="grid grid-cols-2 lg:grid-cols-6 gap-2 text-sm">
                              <input
                                value={setItem.reps}
                                onChange={(e) => handleUpdateSet(exerciseIndex, setIndex, 'reps', e.target.value)}
                                placeholder={`Set ${setIndex + 1} reps`}
                                className="bg-white border border-[var(--nash-border)] rounded-lg px-3 py-2"
                              />
                              <input
                                value={setItem.weight_kg}
                                onChange={(e) => handleUpdateSet(exerciseIndex, setIndex, 'weight_kg', e.target.value)}
                                placeholder="Peso kg"
                                className="bg-white border border-[var(--nash-border)] rounded-lg px-3 py-2"
                              />
                              <input
                                value={setItem.rir}
                                onChange={(e) => handleUpdateSet(exerciseIndex, setIndex, 'rir', e.target.value)}
                                placeholder="RIR"
                                className="bg-white border border-[var(--nash-border)] rounded-lg px-3 py-2"
                              />
                              <input
                                value={setItem.rpe}
                                onChange={(e) => handleUpdateSet(exerciseIndex, setIndex, 'rpe', e.target.value)}
                                placeholder="RPE"
                                className="bg-white border border-[var(--nash-border)] rounded-lg px-3 py-2"
                              />
                              <label className="flex items-center gap-2 rounded-lg border border-[var(--nash-border)] px-3 py-2 text-xs text-[var(--nash-text-muted)]">
                                <input
                                  type="checkbox"
                                  checked={setItem.completed}
                                  onChange={(e) => handleUpdateSet(exerciseIndex, setIndex, 'completed', e.target.checked)}
                                />
                                Hecho
                              </label>
                              <label className="flex items-center gap-2 rounded-lg border border-[var(--nash-border)] px-3 py-2 text-xs text-[var(--nash-text-muted)]">
                                <input
                                  type="checkbox"
                                  checked={setItem.reached_failure}
                                  onChange={(e) => handleUpdateSet(exerciseIndex, setIndex, 'reached_failure', e.target.checked)}
                                />
                                Fallo
                              </label>
                            </div>
                          ))}
                        </div>
                        <input
                          value={exercise.notes}
                          onChange={(e) => handleUpdateExerciseNote(exerciseIndex, e.target.value)}
                          placeholder="Notas del ejercicio"
                          className="w-full bg-white border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                        />
                      </div>
                    ))}
                  </div>

                  <button
                    type="button"
                    onClick={handleAddCustomExercise}
                    className="px-3 py-2 rounded-lg border border-[var(--nash-border)] text-sm cursor-pointer hover:bg-[var(--nash-bg)]"
                  >
                    Agregar ejercicio libre
                  </button>

                  <textarea
                    value={sessionNotes}
                    onChange={(e) => setSessionNotes(e.target.value)}
                    rows={2}
                    placeholder="Notas de sesion: dolor, animo, sueño, interrupciones, ajustes"
                    className="w-full bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                  />
                  {sessionError && <p className="text-xs text-[var(--nash-warning)]">{sessionError}</p>}
                  <button
                    type="submit"
                    disabled={savingSession}
                    className="px-3 py-2 rounded-lg bg-[var(--nash-accent)] text-white text-sm font-medium hover:opacity-90 disabled:opacity-50 cursor-pointer"
                  >
                    {savingSession ? 'Guardando...' : 'Guardar entrenamiento'}
                  </button>
                </form>
              </section>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <section className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded-xl p-5 space-y-5">
                <div>
                  <h3 className="font-semibold text-[var(--nash-text)]">Equipo disponible</h3>
                  <p className="text-xs text-[var(--nash-text-muted)]">
                    Registra lo que si tienes en casa y en gym para que Nash no invente rutinas imposibles.
                  </p>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
                  <div className="bg-[var(--nash-surface-2)] rounded-lg p-3 space-y-2">
                    <p className="font-medium">Casa</p>
                    {equipmentHome.length === 0 && <p className="text-xs text-[var(--nash-text-muted)]">Nada registrado.</p>}
                    {equipmentHome.map((item) => (
                      <div key={item.id} className="flex items-center justify-between gap-2 rounded-lg bg-[var(--nash-bg)] border border-[var(--nash-border)] px-3 py-2">
                        <div>
                          <p>{item.label}</p>
                          <p className="text-xs text-[var(--nash-text-muted)]">{item.category}{item.max_load_kg ? ` · max ${item.max_load_kg}kg` : ''}</p>
                        </div>
                        <button
                          onClick={() => handleDeleteEquipment(item.id)}
                          className="text-xs text-[var(--nash-warning)] cursor-pointer"
                        >
                          Quitar
                        </button>
                      </div>
                    ))}
                  </div>
                  <div className="bg-[var(--nash-surface-2)] rounded-lg p-3 space-y-2">
                    <p className="font-medium">Gym</p>
                    {equipmentGym.length === 0 && <p className="text-xs text-[var(--nash-text-muted)]">Nada registrado.</p>}
                    {equipmentGym.map((item) => (
                      <div key={item.id} className="flex items-center justify-between gap-2 rounded-lg bg-[var(--nash-bg)] border border-[var(--nash-border)] px-3 py-2">
                        <div>
                          <p>{item.label}</p>
                          <p className="text-xs text-[var(--nash-text-muted)]">{item.category}{item.max_load_kg ? ` · max ${item.max_load_kg}kg` : ''}</p>
                        </div>
                        <button
                          onClick={() => handleDeleteEquipment(item.id)}
                          className="text-xs text-[var(--nash-warning)] cursor-pointer"
                        >
                          Quitar
                        </button>
                      </div>
                    ))}
                  </div>
                </div>

                <form onSubmit={handleAddEquipment} className="space-y-2">
                  <p className="text-sm font-medium">Agregar equipo</p>
                  <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
                    <select
                      value={equipmentLocation}
                      onChange={(e) => setEquipmentLocation(e.target.value as 'home' | 'gym')}
                      className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                    >
                      <option value="home">Casa</option>
                      <option value="gym">Gym</option>
                    </select>
                    <select
                      value={equipmentCategory}
                      onChange={(e) => setEquipmentCategory(e.target.value)}
                      className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                    >
                      {EQUIPMENT_CATEGORIES.map((item) => (
                        <option key={item.value} value={item.value}>{item.label}</option>
                      ))}
                    </select>
                    <input
                      value={equipmentMaxLoad}
                      onChange={(e) => setEquipmentMaxLoad(e.target.value)}
                      placeholder="Carga max kg (opc)"
                      className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                    />
                    <input
                      value={equipmentQuantity}
                      onChange={(e) => setEquipmentQuantity(e.target.value)}
                      placeholder="Cantidad"
                      className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                    />
                  </div>
                  <input
                    value={equipmentLabel}
                    onChange={(e) => setEquipmentLabel(e.target.value)}
                    placeholder="Nombre visible (ej: mancuernas ajustables 24kg)"
                    className="w-full bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                  />
                  <input
                    value={equipmentNotes}
                    onChange={(e) => setEquipmentNotes(e.target.value)}
                    placeholder="Notas (opc)"
                    className="w-full bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                  />
                  {equipmentError && <p className="text-xs text-[var(--nash-warning)]">{equipmentError}</p>}
                  <button
                    type="submit"
                    disabled={savingEquipment}
                    className="px-3 py-2 rounded-lg bg-[var(--nash-prussian)] text-white text-sm font-medium hover:opacity-90 disabled:opacity-50 cursor-pointer"
                  >
                    {savingEquipment ? 'Guardando...' : 'Guardar equipo'}
                  </button>
                </form>
              </section>

              <section className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded-xl p-5 space-y-5">
                <div>
                  <h3 className="font-semibold text-[var(--nash-text)]">Mediciones y progreso</h3>
                  <p className="text-xs text-[var(--nash-text-muted)]">
                    Si: vale la pena tomarlas. Lo util es que sean repetibles, no perfectas.
                  </p>
                </div>

                <div className="bg-[var(--nash-surface-2)] rounded-lg p-4 space-y-2 text-sm">
                  {dashboard?.measurement_protocol.why.map((line) => (
                    <p key={line}>{line}</p>
                  ))}
                  <p className="text-[var(--nash-text-muted)]">
                    Mejor momento: {dashboard?.measurement_protocol.timing.best_moment}
                  </p>
                </div>

                <div className="space-y-2 text-xs text-[var(--nash-text-muted)]">
                  {dashboard?.measurement_protocol.rules.map((rule) => (
                    <p key={rule}>{rule}</p>
                  ))}
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {dashboard?.measurement_protocol.sites.map((site) => (
                    <div key={site.code} className="rounded-lg border border-[var(--nash-border)] bg-[var(--nash-bg)] p-3 space-y-1">
                      <p className="text-sm font-medium text-[var(--nash-text)]">{site.label}</p>
                      <p className="text-xs text-[var(--nash-text-muted)]">{site.how}</p>
                    </div>
                  ))}
                </div>

                <form onSubmit={handleAddMeasurement} className="space-y-2">
                  <p className="text-sm font-medium">Guardar medicion</p>
                  <div className="grid grid-cols-2 lg:grid-cols-5 gap-2">
                    <input
                      type="date"
                      value={measurementTakenOn}
                      onChange={(e) => setMeasurementTakenOn(e.target.value)}
                      className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                    />
                    <input
                      value={measurementWeightKg}
                      onChange={(e) => setMeasurementWeightKg(e.target.value)}
                      placeholder="Peso kg"
                      className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                    />
                    <input
                      value={measurementWaistCm}
                      onChange={(e) => setMeasurementWaistCm(e.target.value)}
                      placeholder="Cintura cm"
                      className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                    />
                    <input
                      value={measurementHipCm}
                      onChange={(e) => setMeasurementHipCm(e.target.value)}
                      placeholder="Cadera cm"
                      className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                    />
                    <input
                      value={measurementChestCm}
                      onChange={(e) => setMeasurementChestCm(e.target.value)}
                      placeholder="Pecho cm"
                      className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                    />
                    <input
                      value={measurementArmRelaxedCm}
                      onChange={(e) => setMeasurementArmRelaxedCm(e.target.value)}
                      placeholder="Brazo relajado cm"
                      className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                    />
                    <input
                      value={measurementArmFlexedCm}
                      onChange={(e) => setMeasurementArmFlexedCm(e.target.value)}
                      placeholder="Brazo flex cm"
                      className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                    />
                    <input
                      value={measurementThighCm}
                      onChange={(e) => setMeasurementThighCm(e.target.value)}
                      placeholder="Muslo cm"
                      className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                    />
                    <input
                      value={measurementCalfCm}
                      onChange={(e) => setMeasurementCalfCm(e.target.value)}
                      placeholder="Pantorrilla cm"
                      className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                    />
                    <input
                      value={measurementNotes}
                      onChange={(e) => setMeasurementNotes(e.target.value)}
                      placeholder="Notas"
                      className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                    />
                  </div>
                  {measurementError && <p className="text-xs text-[var(--nash-warning)]">{measurementError}</p>}
                  <button
                    type="submit"
                    disabled={savingMeasurement}
                    className="px-3 py-2 rounded-lg bg-[var(--nash-accent)] text-white text-sm font-medium hover:opacity-90 disabled:opacity-50 cursor-pointer"
                  >
                    {savingMeasurement ? 'Guardando...' : 'Guardar medicion'}
                  </button>
                </form>

                {latestMeasurement && (
                  <div className="rounded-lg border border-[var(--nash-border)] bg-[var(--nash-bg)] p-4 text-sm space-y-2">
                    <p className="font-medium">Ultima medicion ({formatDate(latestMeasurement.taken_on)})</p>
                    <p className="text-[var(--nash-text-muted)]">
                      Peso {latestMeasurement.weight_kg ?? '-'} kg · Cintura {latestMeasurement.waist_cm ?? '-'} cm · Brazo {latestMeasurement.arm_relaxed_cm ?? '-'} cm · Muslo {latestMeasurement.thigh_cm ?? '-'} cm
                    </p>
                    {dashboard?.measurement_change && Object.keys(dashboard.measurement_change).length > 0 && (
                      <p className="text-[var(--nash-text-muted)]">
                        Cambios vs previa: {Object.entries(dashboard.measurement_change).map(([key, value]) => `${key}: ${value > 0 ? '+' : ''}${value}`).join(' · ')}
                      </p>
                    )}
                  </div>
                )}

                <div className="space-y-2">
                  <p className="text-sm font-medium">PRs recientes</p>
                  {(dashboard?.records || []).length === 0 && (
                    <p className="text-xs text-[var(--nash-text-muted)]">Todavia no hay PRs guardados.</p>
                  )}
                  {(dashboard?.records || []).map((record) => (
                    <div key={record.id} className="rounded-lg border border-[var(--nash-border)] bg-[var(--nash-bg)] p-3">
                      <div className="flex items-center justify-between text-sm">
                        <span className="font-medium">{record.exercise_name}</span>
                        <span className="text-xs text-[var(--nash-text-muted)]">{formatDateTime(record.achieved_at)}</span>
                      </div>
                      <p className="text-xs text-[var(--nash-text-muted)] mt-1">
                        {record.weight_kg > 0 ? `${record.weight_kg} kg x ${record.reps}` : `${record.reps} reps`} · {record.metric_type}
                        {record.estimated_1rm ? ` · e1RM ${record.estimated_1rm}` : ''}
                      </p>
                    </div>
                  ))}
                </div>
              </section>
            </div>

            <section className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded-xl p-5 space-y-4">
              <div>
                <h3 className="font-semibold text-[var(--nash-text)]">Historial reciente</h3>
                <p className="text-xs text-[var(--nash-text-muted)]">
                  Esto es lo que Nash podra leer junto con tus diarios para entender adherencia, fatiga y patrones.
                </p>
              </div>
              {(dashboard?.recent_sessions || []).length === 0 && (
                <p className="text-xs text-[var(--nash-text-muted)]">Aun no registras entrenamientos.</p>
              )}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                {(dashboard?.recent_sessions || []).map((session) => (
                  <div key={session.id} className="rounded-lg border border-[var(--nash-border)] bg-[var(--nash-bg)] p-4 space-y-2">
                    <div className="flex items-center justify-between gap-3">
                      <p className="font-medium text-sm">{formatDate(session.date)}</p>
                      <p className="text-xs text-[var(--nash-text-muted)]">
                        {session.level} · {session.actual_location || session.planned_location || 'n/a'} · {session.focus_code || 'sin foco'}
                      </p>
                    </div>
                    <p className="text-xs text-[var(--nash-text-muted)]">
                      Energia {session.energy_level ?? '-'} · RPE {session.session_rpe ?? '-'} · {session.duration_min ?? '-'} min
                    </p>
                    {session.exercise_logs.length > 0 && (
                      <div className="text-xs text-[var(--nash-text-muted)] space-y-1">
                        {session.exercise_logs.slice(0, 4).map((log) => (
                          <p key={`${session.id}-${log.exercise_name}`}>{log.exercise_name}: {log.hard_sets ?? 0} hard sets</p>
                        ))}
                      </div>
                    )}
                    <p className="text-sm">{session.notes || 'Sin notas'}</p>
                  </div>
                ))}
              </div>
            </section>
          </>
        )}
      </div>

      {discoveryMode && (
        <ModuleDiscovery
          module={discoveryMode}
          title={discoveryMode === 'nutrition' ? 'Descubrimiento de Nutricion' : 'Descubrimiento de Ejercicio'}
          subtitle={
            discoveryMode === 'nutrition'
              ? 'Define metas de proteina, peso y habitos alimenticios.'
              : 'Configura nivel, equipo, adherencia y plan minimo/optimo.'
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
