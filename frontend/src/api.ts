const API_BASE = '/api';

export interface SSEMessage {
  type: 'transcript' | 'response' | 'tools' | 'error' | 'done' | 'diary';
  text?: string;
  thread_id?: string;
  transcription_ms?: number;
  diary_entry_id?: number;
  summary?: string;
  audio_play_url?: string;
  calls?: Array<{ name: string; args?: Record<string, unknown>; result?: string }>;
}

export async function uploadAudio(
  audioBlob: Blob,
  entryType: string = 'spontaneous',
  threadId: string = '',
  durationSeconds?: number,
): Promise<ReadableStream<SSEMessage>> {
  const formData = new FormData();
  formData.append('audio', audioBlob, 'recording.webm');
  formData.append('entry_type', entryType);
  formData.append('thread_id', threadId);
  if (durationSeconds != null && durationSeconds > 0) {
    formData.append('duration_s', String(durationSeconds));
  }

  const response = await fetch(`${API_BASE}/audio/upload`, {
    method: 'POST',
    body: formData,
  });

  return parseSSEStream(response);
}

export async function sendChat(
  text: string,
  threadId: string = '',
): Promise<ReadableStream<SSEMessage>> {
  const formData = new FormData();
  formData.append('text', text);
  formData.append('thread_id', threadId);

  const response = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    body: formData,
  });

  return parseSSEStream(response);
}

function parseSSEStream(response: Response): ReadableStream<SSEMessage> {
  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  return new ReadableStream<SSEMessage>({
    async pull(controller) {
      const { done, value } = await reader.read();
      if (done) {
        controller.close();
        return;
      }

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const msg: SSEMessage = JSON.parse(line.slice(6));
            controller.enqueue(msg);
          } catch {
            // skip malformed lines
          }
        }
      }
    },
  });
}

export async function fetchDiary(limit = 20) {
  const res = await fetch(`${API_BASE}/diary?limit=${limit}`);
  return res.json();
}

export async function fetchProfile() {
  const res = await fetch(`${API_BASE}/profile`);
  return res.json();
}

export async function postProfileSynthesize(): Promise<{
  ok?: boolean;
  updated_domains?: string[];
  message?: string;
}> {
  const res = await fetch(`${API_BASE}/profile/synthesize`, { method: 'POST' });
  if (!res.ok) {
    const t = await res.text();
    throw new Error(t || res.statusText);
  }
  return res.json();
}

export async function fetchDebugLast() {
  const res = await fetch(`${API_BASE}/debug/last`);
  return res.json();
}

// Question Engine API

export interface Question {
  id: number;
  question_text: string;
  question_type: string;
  domains_targeted: string[];
  framework: string;
  why_asked: string | null;
  was_answered: number;
}

export async function fetchTodaysQuestions(): Promise<{ questions: Question[] }> {
  const res = await fetch(`${API_BASE}/questions/today`);
  return res.json();
}

export async function generateQuestions(): Promise<{ ok: boolean; questions: Question[] }> {
  const res = await fetch(`${API_BASE}/questions/generate`, { method: 'POST' });
  return res.json();
}

export async function answerQuestion(
  questionId: number,
  audioBlob?: Blob,
  text?: string,
): Promise<{
  ok: boolean;
  answer_id?: number;
  transcript?: string;
  semantic_units?: number;
  richness_score?: number;
  error?: string;
}> {
  const formData = new FormData();
  formData.append('question_id', String(questionId));

  if (audioBlob) {
    formData.append('audio', audioBlob, 'recording.webm');
  }
  if (text) {
    formData.append('text', text);
  }

  const res = await fetch(`${API_BASE}/questions/answer`, {
    method: 'POST',
    body: formData,
  });
  return res.json();
}

export async function fetchQuestionStats(): Promise<{
  stats: Record<string, { total: number; answered: number; avg_richness: number | null }>;
}> {
  const res = await fetch(`${API_BASE}/questions/stats`);
  return res.json();
}

// Self Profile API

export interface SelfProfile {
  id?: number;
  // Core Identity
  birth_date?: string;
  birth_place?: string;
  gender?: string;
  nationality?: string;
  ethnicities?: string;
  preferred_name?: string;
  pronouns?: string;
  // Current Situation
  current_city?: string;
  current_country?: string;
  living_situation?: string;
  years_at_location?: number;
  timezone?: string;
  // Family
  mother_alive?: number;
  mother_age?: number;
  mother_occupation?: string;
  mother_relationship?: string;
  father_alive?: number;
  father_age?: number;
  father_occupation?: string;
  father_relationship?: string;
  parents_status?: string;
  childhood_structure?: string;
  childhood_socioeconomic?: string;
  childhood_location?: string;
  num_siblings?: number;
  birth_order?: string;
  siblings_json?: string;
  // Education
  highest_education?: string;
  field_of_study?: string;
  schools_json?: string;
  // Career
  current_occupation?: string;
  current_industry?: string;
  years_in_role?: number;
  career_satisfaction?: number;
  jobs_json?: string;
  // Relationships
  relationship_status?: string;
  partner_name?: string;
  relationship_years?: number;
  relationship_satisfaction?: number;
  has_children?: number;
  num_children?: number;
  children_json?: string;
  num_past_relationships?: number;
  longest_relationship_years?: number;
  age_first_relationship?: number;
  relationship_patterns_reflection?: string;
  // Health
  height_cm?: number;
  weight_kg?: number;
  chronic_conditions_json?: string;
  medications_json?: string;
  allergies_json?: string;
  mental_health_history_json?: string;
  in_therapy?: number;
  attachment_style?: string;
  // Values & Identity
  core_values_json?: string;
  religious_spiritual?: string;
  religious_practice?: string;
  native_language?: string;
  languages_json?: string;
  mbti?: string;
  big_five_json?: string;
  // Life Story
  life_chapters_json?: string;
  life_theme?: string;
  // Preferences
  communication_style?: string;
  // Financial
  income_bracket?: string;
  owns_home?: number;
  financial_stress?: number;
  // Metadata
  completeness_score?: number;
  section_completeness?: Record<string, number>;
}

export async function fetchSelfProfile(): Promise<{
  profile: SelfProfile | null;
  sections: string[];
  unfilled_fields: string[];
}> {
  const res = await fetch(`${API_BASE}/profile/self`);
  return res.json();
}

export async function updateSelfProfile(updates: Partial<SelfProfile>): Promise<{
  ok: boolean;
  profile: SelfProfile;
  unfilled_fields: string[];
}> {
  const res = await fetch(`${API_BASE}/profile/self`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates),
  });
  return res.json();
}

export async function fetchSelfProfileSections(): Promise<{
  sections: Record<string, string[]>;
}> {
  const res = await fetch(`${API_BASE}/profile/self/sections`);
  return res.json();
}

// Diary Conversations API

export interface ConversationMessage {
  role: 'user' | 'nash';
  content: string;
  audio_path?: string;
}

export interface DiaryConversation {
  diary_entry_id: number;
  messages: ConversationMessage[];
  message_count: number;
  can_continue: boolean;
  max_messages: number;
}

export async function fetchDiaryConversation(entryId: number): Promise<DiaryConversation> {
  const res = await fetch(`${API_BASE}/diary/${entryId}/conversation`);
  return res.json();
}

export async function replyToDiaryEntry(
  entryId: number,
  text?: string,
  audioBlob?: Blob,
): Promise<{
  ok: boolean;
  transcript?: string;
  audio_url?: string;
  nash_reply?: string;
  conversation?: DiaryConversation;
  error?: string;
}> {
  const formData = new FormData();
  if (text) {
    formData.append('text', text);
  }
  if (audioBlob) {
    formData.append('audio', audioBlob, 'recording.webm');
  }

  const res = await fetch(`${API_BASE}/diary/${entryId}/reply`, {
    method: 'POST',
    body: formData,
  });
  return res.json();
}

// =============================================
// Phase 3: Goals + Domains API
// =============================================

export interface LifeDomain {
  id: number;
  code: string;
  name_es: string;
  description_es: string;
  icon: string;
  color: string;
  sort_order: number;
  latest_rating: number | null;
  latest_notes: string | null;
  rated_at: string | null;
}

export type GoalNodeType = 'identity' | 'goal' | 'system' | 'action';
export type GoalHorizon = 'life' | 'annual' | 'quarterly' | 'monthly' | 'weekly';
export type GoalRelationType =
  | 'parent_child'
  | 'related'
  | 'supports'
  | 'depends_on'
  | 'conflicts_with'
  | 'synergy'
  | 'blocks'
  | 'drives'
  | 'requires'
  | 'reinforces'
  | 'costs';

export interface Goal {
  id: number;
  domain_id: number | null;
  domain_code: string | null;
  domain_tags_json?: string | null;
  domain_tags?: string[];
  domain_name: string | null;
  domain_icon: string | null;
  parent_goal_id: number | null;
  node_type: GoalNodeType;
  title: string;
  description: string | null;
  why_matters: string | null;
  horizon: GoalHorizon | null;
  start_date: string | null;
  target_date: string | null;
  cadence_text?: string | null;
  time_cost_min?: number | null;
  energy_cost?: number | null;
  attention_cost?: number | null;
  status: 'active' | 'completed' | 'abandoned' | 'paused';
  progress_pct: number;
  motivation_type: 'external' | 'introjected' | 'identified' | 'intrinsic' | null;
  importance?: number | null;
  difficulty?: number | null;
  commitment?: number | null;
  specificity?: number | null;
  locus_of_control?: 'internal' | 'external' | 'mixed' | null;
  nash_opinion?: string | null;
  coherence_score?: number | null;
  conflicts_json?: string | null;
  synergies_json?: string | null;
  priority_rank?: number | null;
  source?: 'manual' | 'discovery' | null;
  discovery_session_id?: number | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export interface GoalsSummary {
  total: number;
  active: number;
  completed: number;
  by_horizon: Record<string, number>;
  by_domain: Record<string, { name: string; count: number }>;
  by_node_type?: Record<string, number>;
}

export async function fetchLifeDomains(): Promise<{ domains: LifeDomain[] }> {
  const res = await fetch(`${API_BASE}/goals/domains`);
  return res.json();
}

export async function rateDomains(
  ratings: Record<string, number>,
  notes?: string,
): Promise<{ ok: boolean; rated_count?: number; error?: string }> {
  const res = await fetch(`${API_BASE}/goals/domains/rate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ratings, notes }),
  });
  return res.json();
}

export async function fetchDomainHistory(
  domainCode: string,
  limit: number = 30,
): Promise<{ domain: string; history: Array<{ rating: number; notes: string | null; rated_at: string }> }> {
  const res = await fetch(`${API_BASE}/goals/domains/${domainCode}/history?limit=${limit}`);
  return res.json();
}

export async function fetchGoals(filters?: {
  status?: string;
  domain?: string;
  horizon?: string;
  node_type?: GoalNodeType;
  limit?: number;
}): Promise<{ goals: Goal[] }> {
  const params = new URLSearchParams();
  if (filters?.status) params.append('status', filters.status);
  if (filters?.domain) params.append('domain', filters.domain);
  if (filters?.horizon) params.append('horizon', filters.horizon);
  if (filters?.node_type) params.append('node_type', filters.node_type);
  if (filters?.limit) params.append('limit', String(filters.limit));

  const query = params.toString() ? `?${params.toString()}` : '';
  const res = await fetch(`${API_BASE}/goals${query}`);
  return res.json();
}

export async function fetchGoalsSummary(): Promise<GoalsSummary> {
  const res = await fetch(`${API_BASE}/goals/summary`);
  return res.json();
}

export async function createGoal(goal: {
  title: string;
  node_type?: GoalNodeType;
  domain_code?: string;
  domain_tags?: string[];
  parent_goal_id?: number;
  description?: string;
  why_matters?: string;
  horizon?: GoalHorizon | null;
  start_date?: string;
  target_date?: string;
  cadence_text?: string;
  time_cost_min?: number;
  energy_cost?: number;
  attention_cost?: number;
  motivation_type?: string;
  importance?: number;
  difficulty?: number;
  commitment?: number;
  specificity?: number;
  locus_of_control?: 'internal' | 'external' | 'mixed';
  nash_opinion?: string;
  coherence_score?: number;
  conflicts_json?: string;
  synergies_json?: string;
  priority_rank?: number;
}): Promise<{ ok: boolean; goal?: Goal; error?: string }> {
  const res = await fetch(`${API_BASE}/goals`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(goal),
  });
  return res.json();
}

export async function updateGoal(
  goalId: number,
  updates: Partial<Goal> & { domain_code?: string | null; domain_tags?: string[] },
): Promise<{ ok: boolean; goal?: Goal; error?: string }> {
  const res = await fetch(`${API_BASE}/goals/${goalId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates),
  });
  return res.json();
}

export async function deleteGoal(goalId: number): Promise<{ ok: boolean; error?: string }> {
  const res = await fetch(`${API_BASE}/goals/${goalId}`, {
    method: 'DELETE',
  });
  return res.json();
}

export interface GoalGraphEdge {
  id: string;
  source_goal_id: number;
  target_goal_id: number;
  relation_type: GoalRelationType;
  kind: 'parent' | 'relation';
  relation_id: number | null;
  note: string | null;
  weight: number | null;
}

export async function fetchGoalsGraph(status?: string): Promise<{ nodes: Goal[]; edges: GoalGraphEdge[] }> {
  const query = status ? `?status=${encodeURIComponent(status)}` : '';
  const res = await fetch(`${API_BASE}/goals/graph${query}`);
  return res.json();
}

export async function createGoalRelation(payload: {
  source_goal_id: number;
  target_goal_id: number;
  relation_type: Exclude<GoalRelationType, 'parent_child'>;
  note?: string;
  weight?: number;
}): Promise<{ ok: boolean; relation?: GoalGraphEdge; error?: string }> {
  const res = await fetch(`${API_BASE}/goals/relations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return res.json();
}

export async function deleteGoalRelation(relationId: number): Promise<{ ok: boolean; error?: string }> {
  const res = await fetch(`${API_BASE}/goals/relations/${relationId}`, {
    method: 'DELETE',
  });
  return res.json();
}

// =============================================
// Goal Discovery API
// =============================================

export interface DiscoveryMessage {
  role: 'user' | 'nash';
  content: string;
  timestamp: string;
}

export interface ExtractedGoal {
  node_type?: GoalNodeType;
  title: string;
  description?: string;
  domain_code?: string;
  domain_tags?: string[];
  horizon?: GoalHorizon | null;
  start_date?: string;
  target_date?: string;
  cadence_text?: string;
  time_cost_min?: number | null;
  energy_cost?: number | null;
  attention_cost?: number | null;
  importance?: number;
  difficulty?: number;
  commitment?: number;
  motivation_type?: string;
  why_matters?: string;
  nash_opinion?: string;
}

export interface ExtractedGoalRelation {
  source_title: string;
  target_title: string;
  relation_type: Exclude<GoalRelationType, 'parent_child'>;
  note?: string;
}

export interface DiscoverySession {
  id: number;
  started_at: string;
  ended_at: string | null;
  status: 'active' | 'completed' | 'abandoned';
  current_state: string;
  messages: DiscoveryMessage[];
  extracted_goals: ExtractedGoal[];
  extracted_relations: ExtractedGoalRelation[];
  goals_confirmed: number;
  summary: string | null;
}

export async function startGoalDiscovery(): Promise<{
  ok: boolean;
  session?: DiscoverySession;
  resumed?: boolean;
  error?: string;
}> {
  const res = await fetch(`${API_BASE}/goals/discovery/start`, {
    method: 'POST',
  });
  return res.json();
}

export async function getActiveDiscovery(): Promise<{
  ok: boolean;
  session: DiscoverySession | null;
}> {
  const res = await fetch(`${API_BASE}/goals/discovery/active`);
  return res.json();
}

export async function getDiscoverySession(sessionId: number): Promise<{
  ok: boolean;
  session?: DiscoverySession;
  error?: string;
}> {
  const res = await fetch(`${API_BASE}/goals/discovery/${sessionId}`);
  return res.json();
}

export async function chatGoalDiscovery(
  sessionId: number,
  text?: string,
  audioBlob?: Blob,
): Promise<{
  ok: boolean;
  user_message?: string;
  response?: string;
  extracted_goals?: ExtractedGoal[];
  extracted_relations?: ExtractedGoalRelation[];
  session?: DiscoverySession;
  error?: string;
}> {
  const formData = new FormData();

  if (audioBlob) {
    formData.append('audio', audioBlob, 'recording.webm');
  }
  if (text) {
    formData.append('text', text);
  }

  const res = await fetch(`${API_BASE}/goals/discovery/${sessionId}/chat`, {
    method: 'POST',
    body: formData,
  });
  return res.json();
}

export async function saveDiscoveredGoal(
  sessionId: number,
  goal: ExtractedGoal,
): Promise<{ ok: boolean; goal?: Goal; error?: string }> {
  const formData = new FormData();
  formData.append('session_id', String(sessionId));
  formData.append('goal_json', JSON.stringify(goal));

  const res = await fetch(`${API_BASE}/goals/discovery/save`, {
    method: 'POST',
    body: formData,
  });
  return res.json();
}

export async function endGoalDiscovery(sessionId: number): Promise<{
  ok: boolean;
  session?: DiscoverySession;
  error?: string;
}> {
  const res = await fetch(`${API_BASE}/goals/discovery/${sessionId}/end`, {
    method: 'POST',
  });
  return res.json();
}

// =============================================
// Phase 5: Nutrition, Exercise, Finance API
// =============================================

export type ModuleName = 'nutrition' | 'exercise' | 'finance';

export interface ModuleDiscoveryMessage {
  role: 'user' | 'nash';
  content: string;
  timestamp: string;
}

export interface ModuleDiscoverySession {
  id: number;
  module: ModuleName;
  started_at: string;
  ended_at: string | null;
  status: 'active' | 'completed' | 'abandoned';
  messages: ModuleDiscoveryMessage[];
  extracted_data: Record<string, unknown>;
  summary: string | null;
}

export async function startModuleDiscovery(module: ModuleName): Promise<{
  ok: boolean;
  session?: ModuleDiscoverySession;
  resumed?: boolean;
  error?: string;
}> {
  const res = await fetch(`${API_BASE}/${module}/discovery/start`, {
    method: 'POST',
  });
  return res.json();
}

export async function getActiveModuleDiscovery(module: ModuleName): Promise<{
  ok: boolean;
  session: ModuleDiscoverySession | null;
  error?: string;
}> {
  const res = await fetch(`${API_BASE}/${module}/discovery/active`);
  return res.json();
}

export async function chatModuleDiscovery(
  module: ModuleName,
  sessionId: number,
  text?: string,
  audioBlob?: Blob,
): Promise<{
  ok: boolean;
  user_message?: string;
  response?: string;
  extracted_data?: Record<string, unknown>;
  profile_updated?: boolean;
  session?: ModuleDiscoverySession;
  error?: string;
}> {
  const formData = new FormData();
  if (audioBlob) {
    formData.append('audio', audioBlob, 'recording.webm');
  }
  if (text) {
    formData.append('text', text);
  }

  const res = await fetch(`${API_BASE}/${module}/discovery/${sessionId}/chat`, {
    method: 'POST',
    body: formData,
  });
  return res.json();
}

export async function endModuleDiscovery(
  module: ModuleName,
  sessionId: number,
  summary?: string,
): Promise<{
  ok: boolean;
  session?: ModuleDiscoverySession;
  error?: string;
}> {
  const formData = new FormData();
  if (summary) {
    formData.append('summary', summary);
  }

  const res = await fetch(`${API_BASE}/${module}/discovery/${sessionId}/end`, {
    method: 'POST',
    body: formData,
  });
  return res.json();
}

export interface NutritionProfile {
  id: number;
  weight_kg: number | null;
  goal_weight_kg: number | null;
  protein_target_g: number | null;
  calorie_target: number | null;
  carb_target_g: number | null;
  fat_target_g: number | null;
  meals_per_day: number | null;
  eating_window: string | null;
  restrictions_json: string | null;
  supplements_json: string | null;
  notes: string | null;
  discovery_session_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface NutritionDailyTotals {
  protein: number;
  carbs: number;
  fat: number;
  calories: number;
}

export interface FoodEntry {
  id: number;
  timestamp: string;
  description: string;
  meal_type: 'breakfast' | 'lunch' | 'dinner' | 'snack';
  weight_g: number | null;
  protein_g: number | null;
  carbs_g: number | null;
  fat_g: number | null;
  calories: number | null;
  is_estimated: number;
  audio_path: string | null;
  notes: string | null;
}

export async function fetchNutritionProfile(): Promise<{
  profile: NutritionProfile | null;
  daily_totals: NutritionDailyTotals;
}> {
  const res = await fetch(`${API_BASE}/nutrition/profile`);
  return res.json();
}

export async function updateNutritionProfile(
  updates: Partial<NutritionProfile>,
): Promise<{
  ok: boolean;
  profile: NutritionProfile;
  daily_totals: NutritionDailyTotals;
}> {
  const res = await fetch(`${API_BASE}/nutrition/profile`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates),
  });
  return res.json();
}

export async function fetchNutritionEntries(params?: {
  today?: boolean;
  limit?: number;
}): Promise<{
  entries: FoodEntry[];
  daily_totals: NutritionDailyTotals;
}> {
  const search = new URLSearchParams();
  if (params?.today != null) {
    search.append('today', params.today ? '1' : '0');
  }
  if (params?.limit != null) {
    search.append('limit', String(params.limit));
  }
  const query = search.toString() ? `?${search.toString()}` : '';
  const res = await fetch(`${API_BASE}/nutrition/entries${query}`);
  return res.json();
}

export async function createNutritionEntry(input: {
  description: string;
  meal_type?: 'breakfast' | 'lunch' | 'dinner' | 'snack';
  weight_g?: number | null;
  protein_g?: number | null;
  carbs_g?: number | null;
  fat_g?: number | null;
  calories?: number | null;
  notes?: string;
  audioBlob?: Blob;
}): Promise<{
  ok: boolean;
  entry?: FoodEntry;
  daily_totals?: NutritionDailyTotals;
  error?: string;
}> {
  const formData = new FormData();
  formData.append('description', input.description);
  formData.append('meal_type', input.meal_type || 'snack');
  if (input.weight_g != null) formData.append('weight_g', String(input.weight_g));
  if (input.protein_g != null) formData.append('protein_g', String(input.protein_g));
  if (input.carbs_g != null) formData.append('carbs_g', String(input.carbs_g));
  if (input.fat_g != null) formData.append('fat_g', String(input.fat_g));
  if (input.calories != null) formData.append('calories', String(input.calories));
  if (input.notes) formData.append('notes', input.notes);
  if (input.audioBlob) formData.append('audio', input.audioBlob, 'recording.webm');

  const res = await fetch(`${API_BASE}/nutrition/entries`, {
    method: 'POST',
    body: formData,
  });
  return res.json();
}

export interface ExerciseProfile {
  id: number;
  fitness_level: 'beginner' | 'intermediate' | 'advanced' | null;
  equipment_json: string | null;
  workout_days_per_week: number | null;
  time_per_workout_min: number | null;
  minimum_session_min: number | null;
  optimal_session_min: number | null;
  goals_json: string | null;
  limitations_json: string | null;
  schedule_days_json: string | null;
  barriers_json: string | null;
  enjoyment_json: string | null;
  has_gym_access: number | null;
  gym_start_date: string | null;
  mobility_focus: number | null;
  preferred_location: 'home' | 'gym' | 'either' | null;
  preferred_split: 'auto' | 'full_body' | 'upper_lower' | null;
  primary_goal: 'muscle_gain' | 'strength' | 'recomposition' | 'general_fitness' | null;
  height_cm: number | null;
  training_history_notes: string | null;
  notes: string | null;
  discovery_session_id: number | null;
  created_at: string;
  updated_at: string;
  equipment?: string[];
  equipment_categories?: string[];
  equipment_items?: ExerciseEquipmentItem[];
  goals?: string[];
  limitations?: string[];
  schedule_days?: string[];
  barriers?: string[];
  enjoyment?: string[];
}

export interface ExerciseEquipmentItem {
  id: number;
  location: 'home' | 'gym';
  category: string;
  label: string;
  max_load_kg: number | null;
  quantity: number | null;
  notes: string | null;
  is_active: number;
  created_at: string;
  updated_at: string;
}

export interface BodyMeasurementSnapshot {
  id: number;
  taken_on: string;
  weight_kg: number | null;
  waist_cm: number | null;
  hip_cm: number | null;
  chest_cm: number | null;
  arm_relaxed_cm: number | null;
  arm_flexed_cm: number | null;
  thigh_cm: number | null;
  calf_cm: number | null;
  notes: string | null;
  created_at: string;
}

export interface ExerciseSetLog {
  reps: number | null;
  weight_kg: number;
  rir: number | null;
  rpe: number | null;
  reached_failure: boolean;
  completed: boolean;
  notes?: string | null;
}

export interface ExerciseLogEntry {
  id?: number;
  session_id?: number;
  exercise_name: string;
  movement_pattern?: string | null;
  equipment_context?: string | null;
  location?: 'home' | 'gym' | null;
  volume_load?: number | null;
  hard_sets?: number | null;
  best_set_weight_kg?: number | null;
  best_set_reps?: number | null;
  notes?: string | null;
  is_personal_record?: number;
  sets_json?: string;
  sets: ExerciseSetLog[];
}

export interface PersonalRecord {
  id: number;
  exercise_name: string;
  weight_kg: number;
  reps: number;
  metric_type: 'estimated_1rm' | 'load_reps' | 'repetition';
  estimated_1rm: number | null;
  session_id: number | null;
  notes: string | null;
  achieved_at: string;
}

export interface WorkoutTemplate {
  id: number;
  name: string;
  level: 'minimum' | 'optimal';
  workout_type: string | null;
  exercises_json: string;
  estimated_duration_min: number | null;
  is_active: number;
  created_at: string;
  exercises: Array<Record<string, unknown>>;
}

export interface WorkoutSession {
  id: number;
  date: string;
  level: 'minimum' | 'optimal';
  template_id: number | null;
  template_name: string | null;
  focus_code: string | null;
  planned_location: 'home' | 'gym' | null;
  actual_location: 'home' | 'gym' | null;
  duration_min: number | null;
  exercises_json: string | null;
  notes: string | null;
  energy_level: number | null;
  session_rpe: number | null;
  fallback_used: number;
  plan_source: 'manual' | 'generated' | 'template';
  completed: number;
  created_at: string;
  exercises: Array<Record<string, unknown>>;
  exercise_logs: ExerciseLogEntry[];
}

export interface WorkoutPlanExercise {
  name: string;
  movement_pattern: string;
  equipment_context: string;
  exercise_type: string;
  sets: number;
  rep_range: string;
  rest_sec: number;
  rir_target: string;
  failure_guidance: string;
  coaching: string;
  progression_tip: string;
  last_performance?: {
    date?: string;
    level?: string;
    location?: string;
    best_set?: {
      reps: number;
      weight_kg: number;
      rir?: number | null;
      reached_failure?: boolean;
    } | null;
  } | null;
}

export interface WorkoutPlanSession {
  name: string;
  level: 'minimum' | 'optimal';
  location: 'home' | 'gym';
  focus_code: string;
  goal: string;
  estimated_duration_min: number;
  warmup: string[];
  guidance: string[];
  exercises: WorkoutPlanExercise[];
  extra_energy_enabled: boolean;
}

export interface WorkoutPlan {
  generated_at: string;
  input: {
    location: 'home' | 'gym';
    energy_level: number;
    available_time_min: number;
    desired_mode: 'minimum' | 'optimal' | 'auto' | string;
  };
  training_target: {
    primary_goal: string;
    weekly_sessions_target: number;
    minimum_sessions_floor: number;
    hard_sets_goal_per_muscle: string;
    phase: 'foundation' | 'build';
  };
  primary_session: WorkoutPlanSession;
  fallback_session: WorkoutPlanSession;
  weekly_outline: Array<{
    day: string;
    session: string;
    location: string;
    focus_code: string;
  }>;
  adherence: {
    last_7_days: Record<string, unknown>;
    last_28_days: Record<string, unknown>;
  };
  nutrition_bridge: {
    protein_today_g: number;
    protein_target_g: number;
    protein_progress_pct: number | null;
  };
  notes: string[];
}

export interface MeasurementProtocol {
  recommended: boolean;
  why: string[];
  timing: {
    baseline: string;
    frequency: string;
    best_moment: string;
  };
  rules: string[];
  sites: Array<{
    code: string;
    label: string;
    how: string;
    source_note: string;
  }>;
}

export interface ExerciseDashboard {
  profile: ExerciseProfile | null;
  equipment: ExerciseEquipmentItem[];
  measurements: BodyMeasurementSnapshot[];
  latest_measurement: BodyMeasurementSnapshot | null;
  measurement_change: Record<string, number>;
  records: PersonalRecord[];
  recent_sessions: WorkoutSession[];
  adherence_7: Record<string, unknown>;
  adherence_28: Record<string, unknown>;
  measurement_protocol: MeasurementProtocol;
  today_plan: WorkoutPlan;
}

export async function fetchExerciseProfile(): Promise<{
  profile: ExerciseProfile | null;
}> {
  const res = await fetch(`${API_BASE}/exercise/profile`);
  return res.json();
}

export async function updateExerciseProfile(
  updates: Partial<ExerciseProfile>,
): Promise<{ ok: boolean; profile: ExerciseProfile }> {
  const res = await fetch(`${API_BASE}/exercise/profile`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates),
  });
  return res.json();
}

export async function fetchExerciseDashboard(): Promise<ExerciseDashboard> {
  const res = await fetch(`${API_BASE}/exercise/dashboard`);
  return res.json();
}

export async function generateWorkoutPlan(input: {
  location?: 'home' | 'gym';
  energy_level?: number;
  available_time_min?: number;
  desired_mode?: 'minimum' | 'optimal' | 'auto';
}): Promise<{ ok: boolean; plan: WorkoutPlan }> {
  const res = await fetch(`${API_BASE}/exercise/plan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });
  return res.json();
}

export async function fetchExerciseEquipment(location?: 'home' | 'gym'): Promise<{
  items: ExerciseEquipmentItem[];
}> {
  const query = location ? `?location=${location}` : '';
  const res = await fetch(`${API_BASE}/exercise/equipment${query}`);
  return res.json();
}

export async function createExerciseEquipment(input: {
  location: 'home' | 'gym';
  category: string;
  label: string;
  max_load_kg?: number;
  quantity?: number;
  notes?: string;
}): Promise<{ ok: boolean; item?: ExerciseEquipmentItem; error?: string }> {
  const res = await fetch(`${API_BASE}/exercise/equipment`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });
  return res.json();
}

export async function deleteExerciseEquipment(id: number): Promise<{ ok: boolean }> {
  const res = await fetch(`${API_BASE}/exercise/equipment/${id}`, {
    method: 'DELETE',
  });
  return res.json();
}

export async function fetchExerciseMeasurements(limit: number = 12): Promise<{
  measurements: BodyMeasurementSnapshot[];
}> {
  const res = await fetch(`${API_BASE}/exercise/measurements?limit=${limit}`);
  return res.json();
}

export async function createExerciseMeasurement(input: Partial<BodyMeasurementSnapshot>): Promise<{
  ok: boolean;
  measurement?: BodyMeasurementSnapshot;
}> {
  const res = await fetch(`${API_BASE}/exercise/measurements`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });
  return res.json();
}

export async function fetchExerciseRecords(limit: number = 20): Promise<{
  records: PersonalRecord[];
}> {
  const res = await fetch(`${API_BASE}/exercise/records?limit=${limit}`);
  return res.json();
}

export async function fetchWorkoutTemplates(level?: 'minimum' | 'optimal'): Promise<{
  templates: WorkoutTemplate[];
}> {
  const query = level ? `?level=${level}` : '';
  const res = await fetch(`${API_BASE}/exercise/templates${query}`);
  return res.json();
}

export async function createWorkoutTemplate(input: {
  name: string;
  level: 'minimum' | 'optimal';
  workout_type?: string;
  estimated_duration_min?: number;
  exercises: Array<Record<string, unknown>>;
}): Promise<{ ok: boolean; template?: WorkoutTemplate; error?: string }> {
  const res = await fetch(`${API_BASE}/exercise/templates`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });
  return res.json();
}

export async function fetchWorkoutSessions(limit: number = 30): Promise<{
  sessions: WorkoutSession[];
}> {
  const res = await fetch(`${API_BASE}/exercise/sessions?limit=${limit}`);
  return res.json();
}

export async function createWorkoutSession(input: {
  date?: string;
  level: 'minimum' | 'optimal';
  template_id?: number;
  focus_code?: string;
  planned_location?: 'home' | 'gym';
  actual_location?: 'home' | 'gym';
  duration_min?: number;
  exercises?: Array<Record<string, unknown>>;
  notes?: string;
  energy_level?: number;
  session_rpe?: number;
  fallback_used?: boolean;
  plan_source?: 'manual' | 'generated' | 'template';
  completed?: number;
  exercise_logs?: ExerciseLogEntry[];
}): Promise<{ ok: boolean; session?: WorkoutSession; error?: string }> {
  const res = await fetch(`${API_BASE}/exercise/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });
  return res.json();
}

export interface FinanceProfile {
  id: number;
  monthly_income: number | null;
  currency: string | null;
  fixed_expenses_json: string | null;
  debts_json: string | null;
  savings_goal: number | null;
  emergency_fund_target: number | null;
  notes: string | null;
  discovery_session_id: number | null;
  created_at: string;
  updated_at: string;
  fixed_expenses?: Array<Record<string, unknown>>;
  debts?: Array<Record<string, unknown>>;
}

export interface ExpenseCategory {
  id: number;
  code: string;
  name_es: string;
  icon: string;
  color: string;
  is_fixed: number;
  sort_order: number;
}

export interface ExpenseEntry {
  id: number;
  timestamp: string;
  description: string;
  amount: number;
  category_id: number | null;
  category_code: string | null;
  category_name: string | null;
  category_icon: string | null;
  is_recurring: number;
  notes: string | null;
  payment_method: string | null;
}

export interface FinanceSummary {
  total: number;
  by_category: Array<{
    code: string | null;
    name_es: string | null;
    icon: string | null;
    total: number;
  }>;
}

export async function fetchFinanceProfile(): Promise<{
  profile: FinanceProfile | null;
}> {
  const res = await fetch(`${API_BASE}/finance/profile`);
  return res.json();
}

export async function updateFinanceProfile(
  updates: Partial<FinanceProfile>,
): Promise<{ ok: boolean; profile: FinanceProfile }> {
  const res = await fetch(`${API_BASE}/finance/profile`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates),
  });
  return res.json();
}

export async function fetchExpenseCategories(): Promise<{
  categories: ExpenseCategory[];
}> {
  const res = await fetch(`${API_BASE}/finance/categories`);
  return res.json();
}

export async function fetchExpenses(params?: {
  limit?: number;
  month?: string;
}): Promise<{ expenses: ExpenseEntry[] }> {
  const search = new URLSearchParams();
  if (params?.limit != null) search.append('limit', String(params.limit));
  if (params?.month) search.append('month', params.month);
  const query = search.toString() ? `?${search.toString()}` : '';
  const res = await fetch(`${API_BASE}/finance/expenses${query}`);
  return res.json();
}

export async function createExpense(input: {
  description: string;
  amount: number;
  category_code?: string;
  is_recurring?: boolean;
  notes?: string;
  payment_method?: string;
  timestamp?: string;
}): Promise<{
  ok: boolean;
  expense?: ExpenseEntry;
  summary?: FinanceSummary;
  error?: string;
}> {
  const res = await fetch(`${API_BASE}/finance/expenses`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });
  return res.json();
}

export async function fetchFinanceSummary(month?: string): Promise<{
  summary: FinanceSummary;
}> {
  const query = month ? `?month=${encodeURIComponent(month)}` : '';
  const res = await fetch(`${API_BASE}/finance/summary${query}`);
  return res.json();
}
