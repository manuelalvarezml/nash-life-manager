import json
import sqlite3
from datetime import datetime, timedelta

import aiosqlite
from backend.config import DB_PATH

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS diary_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    entry_type TEXT NOT NULL CHECK (entry_type IN ('morning', 'night', 'spontaneous')),
    raw_transcript TEXT NOT NULL,
    summary TEXT,
    domain_tags TEXT,  -- JSON array
    energy_level INTEGER CHECK (energy_level BETWEEN 1 AND 10),
    audio_path TEXT,
    duration_s REAL
);

CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    topic TEXT NOT NULL,
    raw_transcript TEXT NOT NULL,
    life_period TEXT CHECK (life_period IN ('childhood', 'adolescence', 'youth', 'present', 'unspecified')),
    chroma_id TEXT,
    audio_path TEXT,
    diary_entry_id INTEGER REFERENCES diary_entries(id),
    semantic_unit_id INTEGER REFERENCES semantic_units(id),
    title TEXT,
    occurred_year_start INTEGER,
    occurred_year_end INTEGER,
    age_start INTEGER,
    age_end INTEGER,
    place_name TEXT,
    people_json TEXT NOT NULL DEFAULT '[]',
    themes_json TEXT NOT NULL DEFAULT '[]',
    emotional_valence TEXT,
    memory_type TEXT,
    significance INTEGER CHECK (significance IS NULL OR significance BETWEEN 1 AND 5),
    sensory_details TEXT,
    confidence REAL CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
    user_verified INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS profile_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT NOT NULL UNIQUE,
    summary_text TEXT NOT NULL DEFAULT '',
    last_updated TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS profile_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT NOT NULL,
    statement TEXT NOT NULL,
    fact_type TEXT NOT NULL CHECK (fact_type IN ('declared', 'behavioral', 'inferred', 'contradicted')),
    source_type TEXT,
    evidence_count INTEGER NOT NULL DEFAULT 1,
    confidence TEXT NOT NULL DEFAULT 'emerging' CHECK (confidence IN ('emerging', 'developing', 'established')),
    weight REAL NOT NULL DEFAULT 0.5,
    contradicts_fact_id INTEGER REFERENCES profile_facts(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_updated TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS insights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    content TEXT NOT NULL,
    related_domains TEXT,  -- JSON array
    confidence TEXT NOT NULL DEFAULT 'emerging',
    was_read INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS semantic_units (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    diary_entry_id INTEGER REFERENCES diary_entries(id),
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    unit_type TEXT NOT NULL,
    content TEXT NOT NULL,
    life_period TEXT,
    age_referenced INTEGER,
    topics TEXT NOT NULL DEFAULT '[]',
    emotional_valence TEXT,
    domains TEXT NOT NULL DEFAULT '[]',
    insight_potential TEXT NOT NULL DEFAULT 'low',
    chroma_id TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS asked_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    question_text TEXT NOT NULL,
    question_type TEXT NOT NULL,
    domains_targeted TEXT NOT NULL DEFAULT '[]',
    framework TEXT NOT NULL,
    why_asked TEXT,
    answer_entry_id INTEGER REFERENCES daily_question_answers(id),
    response_richness_score REAL,
    was_answered INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS daily_question_answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id INTEGER NOT NULL REFERENCES asked_questions(id),
    raw_transcript TEXT NOT NULL,
    semantic_units_extracted TEXT NOT NULL DEFAULT '[]',
    answered_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS diary_conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    diary_entry_id INTEGER NOT NULL REFERENCES diary_entries(id),
    messages_json TEXT NOT NULL DEFAULT '[]',
    message_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_diary_conversations_entry ON diary_conversations(diary_entry_id);

-- =============================================
-- PHASE 3: Goals + Calendar + Time
-- =============================================

-- Life domains based on Wheel of Life (predefined, seeded)
CREATE TABLE IF NOT EXISTS life_domains (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,          -- 'career', 'health', etc.
    name_es TEXT NOT NULL,              -- 'Carrera', 'Salud', etc.
    description_es TEXT,
    icon TEXT,                          -- emoji or icon name
    color TEXT,                         -- hex color for UI
    sort_order INTEGER NOT NULL DEFAULT 0
);

-- Domain satisfaction ratings over time
CREATE TABLE IF NOT EXISTS domain_ratings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain_id INTEGER NOT NULL REFERENCES life_domains(id),
    rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 10),
    notes TEXT,
    rated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_domain_ratings_domain ON domain_ratings(domain_id);
CREATE INDEX IF NOT EXISTS idx_domain_ratings_date ON domain_ratings(rated_at);

-- Goals (Phase 3a: basic, Phase 3b adds hierarchy)
CREATE TABLE IF NOT EXISTS goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain_id INTEGER REFERENCES life_domains(id),
    domain_tags_json TEXT DEFAULT '[]',
    parent_goal_id INTEGER REFERENCES goals(id),
    node_type TEXT NOT NULL DEFAULT 'goal'
        CHECK (node_type IN ('identity', 'goal', 'system', 'action')),

    -- Core fields
    title TEXT NOT NULL,
    description TEXT,
    why_matters TEXT,                   -- Self-concordance: why this goal?

    -- Time horizon
    horizon TEXT
        CHECK (horizon IS NULL OR horizon IN ('life', 'annual', 'quarterly', 'monthly', 'weekly')),
    start_date TEXT,                    -- Optional start date
    target_date TEXT,                   -- Optional deadline
    cadence_text TEXT,                  -- For system/process nodes
    time_cost_min INTEGER CHECK (time_cost_min IS NULL OR time_cost_min >= 0),
    energy_cost INTEGER CHECK (energy_cost IS NULL OR energy_cost BETWEEN 1 AND 5),
    attention_cost INTEGER CHECK (attention_cost IS NULL OR attention_cost BETWEEN 1 AND 5),

    -- Status
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'completed', 'abandoned', 'paused')),
    progress_pct INTEGER NOT NULL DEFAULT 0 CHECK (progress_pct BETWEEN 0 AND 100),

    -- Self-concordance (Phase 3c)
    motivation_type TEXT CHECK (motivation_type IN ('external', 'introjected', 'identified', 'intrinsic')),

    -- Goal Discovery fields (research-validated attributes)
    importance INTEGER CHECK (importance BETWEEN 1 AND 10),       -- Personal significance
    difficulty INTEGER CHECK (difficulty BETWEEN 1 AND 10),       -- Challenge level
    commitment INTEGER CHECK (commitment BETWEEN 1 AND 10),       -- Determination to pursue
    specificity INTEGER CHECK (specificity BETWEEN 1 AND 10),     -- How concrete/measurable
    locus_of_control TEXT CHECK (locus_of_control IN ('internal', 'external', 'mixed')),

    -- Nash analysis fields
    nash_opinion TEXT,                  -- Nash's analysis/opinion on this goal
    coherence_score REAL,               -- 0-100, how well it fits with other goals
    conflicts_json TEXT DEFAULT '[]',   -- JSON array of {goal_id, type, note}
    synergies_json TEXT DEFAULT '[]',   -- JSON array of {goal_id, type, note}
    priority_rank INTEGER,              -- Suggested priority order

    -- Source tracking
    source TEXT DEFAULT 'manual' CHECK (source IN ('manual', 'discovery')),
    discovery_session_id INTEGER REFERENCES goal_discovery_sessions(id),

    -- Timestamps
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_goals_domain ON goals(domain_id);
CREATE INDEX IF NOT EXISTS idx_goals_status ON goals(status);
CREATE INDEX IF NOT EXISTS idx_goals_horizon ON goals(horizon);

-- Goal relations graph (non-hierarchical links between goals)
CREATE TABLE IF NOT EXISTS goal_relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_goal_id INTEGER NOT NULL REFERENCES goals(id),
    target_goal_id INTEGER NOT NULL REFERENCES goals(id),
    relation_type TEXT NOT NULL DEFAULT 'related'
        CHECK (relation_type IN (
            'related', 'supports', 'depends_on', 'conflicts_with', 'synergy', 'blocks',
            'drives', 'requires', 'reinforces', 'costs'
        )),
    weight REAL,
    note TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(source_goal_id, target_goal_id, relation_type)
);

CREATE INDEX IF NOT EXISTS idx_goal_relations_source ON goal_relations(source_goal_id);
CREATE INDEX IF NOT EXISTS idx_goal_relations_target ON goal_relations(target_goal_id);

-- Goal Discovery Sessions (conversational goal exploration)
CREATE TABLE IF NOT EXISTS goal_discovery_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    ended_at TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed', 'abandoned')),
    current_state TEXT DEFAULT 'engage',  -- engage, explore, extract, review
    messages_json TEXT NOT NULL DEFAULT '[]',  -- Full conversation [{role, content, timestamp}]
    extracted_goals_json TEXT DEFAULT '[]',    -- Goals identified so far (before confirmation)
    extracted_relations_json TEXT DEFAULT '[]',-- Relations identified so far (before confirmation)
    context_snapshot TEXT,                     -- Profile context at session start
    goals_confirmed INTEGER DEFAULT 0,         -- Number of goals confirmed/saved
    summary TEXT                               -- Session summary when complete
);

CREATE INDEX IF NOT EXISTS idx_discovery_sessions_status ON goal_discovery_sessions(status);

-- =============================================
-- CALENDAR: commands -> suggestions -> commitments
-- =============================================

CREATE TABLE IF NOT EXISTS schedule_preferences (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    timezone TEXT NOT NULL DEFAULT 'America/Lima',
    day_start_time TEXT NOT NULL DEFAULT '08:00',
    day_end_time TEXT NOT NULL DEFAULT '23:00',
    focus_window_start TEXT DEFAULT '09:00',
    focus_window_end TEXT DEFAULT '13:00',
    default_task_duration_min INTEGER NOT NULL DEFAULT 30,
    transition_buffer_min INTEGER NOT NULL DEFAULT 10,
    max_scheduled_min_per_day INTEGER NOT NULL DEFAULT 480,
    preferred_work_days_json TEXT NOT NULL DEFAULT '[0,1,2,3,4]',
    protected_windows_json TEXT NOT NULL DEFAULT '[]',
    notes TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS schedule_inputs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    input_mode TEXT NOT NULL DEFAULT 'text' CHECK (input_mode IN ('text', 'audio', 'diary', 'engine')),
    raw_text TEXT NOT NULL,
    audio_path TEXT,
    command_type TEXT,
    interpretation_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'received' CHECK (status IN ('received', 'processed', 'needs_review', 'failed')),
    result_json TEXT NOT NULL DEFAULT '{}',
    processed_at TEXT
);

CREATE TABLE IF NOT EXISTS calendar_series (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    item_type TEXT NOT NULL DEFAULT 'routine' CHECK (item_type IN ('event', 'task', 'focus', 'routine', 'reminder')),
    recurrence_json TEXT NOT NULL,
    preferred_time TEXT,
    duration_min INTEGER NOT NULL DEFAULT 30 CHECK (duration_min > 0),
    first_date TEXT NOT NULL,
    until_date TEXT,
    source_kind TEXT NOT NULL DEFAULT 'direct',
    source_id INTEGER,
    source_key TEXT,
    goal_id INTEGER REFERENCES goals(id),
    domain_code TEXT,
    priority INTEGER NOT NULL DEFAULT 3 CHECK (priority BETWEEN 1 AND 5),
    flexibility TEXT NOT NULL DEFAULT 'movable' CHECK (flexibility IN ('fixed', 'movable', 'free')),
    energy_required INTEGER CHECK (energy_required IS NULL OR energy_required BETWEEN 1 AND 5),
    location TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS calendar_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    series_id INTEGER REFERENCES calendar_series(id),
    title TEXT NOT NULL,
    description TEXT,
    item_type TEXT NOT NULL DEFAULT 'task' CHECK (item_type IN ('event', 'task', 'focus', 'routine', 'reminder')),
    start_at TEXT,
    end_at TEXT,
    due_at TEXT,
    all_day INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'planned' CHECK (status IN ('planned', 'completed', 'skipped', 'cancelled')),
    source_kind TEXT NOT NULL DEFAULT 'direct',
    source_id INTEGER,
    source_key TEXT,
    goal_id INTEGER REFERENCES goals(id),
    domain_code TEXT,
    priority INTEGER NOT NULL DEFAULT 3 CHECK (priority BETWEEN 1 AND 5),
    flexibility TEXT NOT NULL DEFAULT 'movable' CHECK (flexibility IN ('fixed', 'movable', 'free')),
    energy_required INTEGER CHECK (energy_required IS NULL OR energy_required BETWEEN 1 AND 5),
    location TEXT,
    rationale TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at TEXT,
    UNIQUE(series_id, start_at)
);

CREATE TABLE IF NOT EXISTS calendar_suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_at TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    proposal_type TEXT NOT NULL DEFAULT 'create_item' CHECK (proposal_type IN ('create_item', 'create_series', 'update_item', 'rearrange')),
    source_kind TEXT NOT NULL,
    source_id INTEGER,
    source_key TEXT,
    fingerprint TEXT NOT NULL UNIQUE,
    target_item_id INTEGER REFERENCES calendar_items(id),
    target_series_id INTEGER REFERENCES calendar_series(id),
    title TEXT NOT NULL,
    description TEXT,
    proposed_start_at TEXT,
    proposed_end_at TEXT,
    due_at TEXT,
    duration_min INTEGER,
    item_type TEXT NOT NULL DEFAULT 'task',
    recurrence_json TEXT,
    goal_id INTEGER REFERENCES goals(id),
    domain_code TEXT,
    priority INTEGER NOT NULL DEFAULT 3,
    flexibility TEXT NOT NULL DEFAULT 'movable',
    energy_required INTEGER,
    location TEXT,
    confidence REAL,
    rationale TEXT,
    payload_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS calendar_item_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL REFERENCES calendar_items(id),
    changed_at TEXT NOT NULL DEFAULT (datetime('now')),
    change_type TEXT NOT NULL,
    before_json TEXT NOT NULL DEFAULT '{}',
    after_json TEXT NOT NULL DEFAULT '{}',
    reason TEXT,
    schedule_input_id INTEGER REFERENCES schedule_inputs(id)
);

CREATE INDEX IF NOT EXISTS idx_calendar_items_start ON calendar_items(start_at);
CREATE INDEX IF NOT EXISTS idx_calendar_items_status ON calendar_items(status);
CREATE INDEX IF NOT EXISTS idx_calendar_items_source ON calendar_items(source_kind, source_id);
CREATE INDEX IF NOT EXISTS idx_calendar_suggestions_status ON calendar_suggestions(status, created_at);
CREATE INDEX IF NOT EXISTS idx_calendar_series_active ON calendar_series(active);

-- =============================================
-- PHASE 5: Nutricion, Ejercicio, Dinero
-- =============================================

-- Nutrition profile (from discovery conversation)
CREATE TABLE IF NOT EXISTS nutrition_profile (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    weight_kg REAL,
    goal_weight_kg REAL,
    protein_target_g INTEGER,
    calorie_target INTEGER,
    carb_target_g INTEGER,
    fat_target_g INTEGER,
    meals_per_day INTEGER DEFAULT 3,
    eating_window TEXT,                    -- e.g., "8am-8pm"
    restrictions_json TEXT DEFAULT '[]',   -- ["vegetarian", "lactose-free"]
    supplements_json TEXT DEFAULT '[]',
    notes TEXT,
    discovery_session_id INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Food entries (meals logged)
CREATE TABLE IF NOT EXISTS food_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    meal_type TEXT CHECK (meal_type IN ('breakfast', 'lunch', 'dinner', 'snack')),
    description TEXT NOT NULL,
    weight_g REAL,
    protein_g REAL,
    carbs_g REAL,
    fat_g REAL,
    calories REAL,
    is_estimated INTEGER DEFAULT 1,        -- Whether macros were estimated
    audio_path TEXT,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_food_entries_date ON food_entries(date(timestamp));

-- Exercise profile (from discovery conversation)
CREATE TABLE IF NOT EXISTS exercise_profile (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fitness_level TEXT CHECK (fitness_level IN ('beginner', 'intermediate', 'advanced')),
    equipment_json TEXT DEFAULT '[]',      -- ["dumbbells", "bands", "pullup_bar"]
    workout_days_per_week INTEGER DEFAULT 3,
    time_per_workout_min INTEGER DEFAULT 45,
    minimum_session_min INTEGER DEFAULT 12,
    optimal_session_min INTEGER DEFAULT 45,
    goals_json TEXT DEFAULT '[]',          -- ["muscle_gain", "mobility", "strength"]
    limitations_json TEXT DEFAULT '[]',    -- injuries, conditions
    schedule_days_json TEXT DEFAULT '[]',
    barriers_json TEXT DEFAULT '[]',
    enjoyment_json TEXT DEFAULT '[]',
    has_gym_access INTEGER DEFAULT 0,
    gym_start_date TEXT,
    mobility_focus INTEGER DEFAULT 1,      -- desk/bed lifestyle needs this
    preferred_location TEXT DEFAULT 'either'
        CHECK (preferred_location IN ('home', 'gym', 'either')),
    preferred_split TEXT DEFAULT 'auto'
        CHECK (preferred_split IN ('auto', 'full_body', 'upper_lower')),
    primary_goal TEXT DEFAULT 'muscle_gain'
        CHECK (primary_goal IN ('muscle_gain', 'strength', 'recomposition', 'general_fitness')),
    height_cm REAL,
    training_history_notes TEXT,
    notes TEXT,
    discovery_session_id INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS exercise_equipment_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    location TEXT NOT NULL CHECK (location IN ('home', 'gym')),
    category TEXT NOT NULL,
    label TEXT NOT NULL,
    max_load_kg REAL,
    quantity INTEGER DEFAULT 1,
    notes TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_exercise_equipment_location ON exercise_equipment_items(location);

-- Workout templates (generated or custom)
CREATE TABLE IF NOT EXISTS workout_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    level TEXT NOT NULL CHECK (level IN ('minimum', 'optimal')),
    workout_type TEXT,                     -- push, pull, legs, full, mobility
    exercises_json TEXT NOT NULL,          -- [{name, sets, reps, rest_sec, notes}]
    estimated_duration_min INTEGER,
    is_active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Workout sessions (actual workouts done)
CREATE TABLE IF NOT EXISTS workout_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    template_id INTEGER REFERENCES workout_templates(id),
    level TEXT NOT NULL CHECK (level IN ('minimum', 'optimal')),
    focus_code TEXT,
    planned_location TEXT CHECK (planned_location IN ('home', 'gym')),
    actual_location TEXT CHECK (actual_location IN ('home', 'gym')),
    started_at TEXT,
    ended_at TEXT,
    duration_min INTEGER,
    exercises_json TEXT,                   -- Actual exercises performed
    notes TEXT,
    energy_level INTEGER CHECK (energy_level BETWEEN 1 AND 10),
    session_rpe INTEGER CHECK (session_rpe BETWEEN 1 AND 10),
    fallback_used INTEGER DEFAULT 0,
    plan_source TEXT DEFAULT 'manual' CHECK (plan_source IN ('manual', 'generated', 'template')),
    completed INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_workout_sessions_date ON workout_sessions(date);

-- Exercise logs (detailed per exercise)
CREATE TABLE IF NOT EXISTS exercise_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER REFERENCES workout_sessions(id),
    exercise_name TEXT NOT NULL,
    sets_json TEXT NOT NULL,               -- [{reps, weight_kg, rpe}]
    movement_pattern TEXT,
    equipment_context TEXT,
    location TEXT CHECK (location IN ('home', 'gym')),
    volume_load REAL,
    hard_sets INTEGER,
    best_set_weight_kg REAL,
    best_set_reps INTEGER,
    notes TEXT,
    is_personal_record INTEGER DEFAULT 0
);

-- Personal records
CREATE TABLE IF NOT EXISTS personal_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exercise_name TEXT NOT NULL,
    weight_kg REAL NOT NULL,
    reps INTEGER NOT NULL,
    metric_type TEXT DEFAULT 'estimated_1rm'
        CHECK (metric_type IN ('estimated_1rm', 'load_reps', 'repetition')),
    estimated_1rm REAL,
    session_id INTEGER REFERENCES workout_sessions(id),
    notes TEXT,
    achieved_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_personal_records_exercise ON personal_records(exercise_name);

CREATE TABLE IF NOT EXISTS body_measurement_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    taken_on TEXT NOT NULL,
    weight_kg REAL,
    waist_cm REAL,
    hip_cm REAL,
    chest_cm REAL,
    arm_relaxed_cm REAL,
    arm_flexed_cm REAL,
    thigh_cm REAL,
    calf_cm REAL,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_body_measurements_taken_on ON body_measurement_snapshots(taken_on);

-- Finance profile (from discovery conversation)
CREATE TABLE IF NOT EXISTS finance_profile (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    monthly_income REAL,
    currency TEXT DEFAULT 'PEN',
    fixed_expenses_json TEXT DEFAULT '[]', -- [{name, amount, due_day}]
    debts_json TEXT DEFAULT '[]',          -- [{name, total, remaining, interest_rate, min_payment}]
    savings_goal REAL,
    emergency_fund_target REAL,
    notes TEXT,
    discovery_session_id INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Expense categories
CREATE TABLE IF NOT EXISTS expense_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name_es TEXT NOT NULL,
    icon TEXT,
    color TEXT,
    is_fixed INTEGER DEFAULT 0,
    budget_amount REAL,
    sort_order INTEGER DEFAULT 0
);

-- Expense entries
CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    description TEXT NOT NULL,
    amount REAL NOT NULL,
    category_id INTEGER REFERENCES expense_categories(id),
    is_recurring INTEGER DEFAULT 0,
    notes TEXT,
    payment_method TEXT                    -- cash, debit, credit
);

CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date(timestamp));
CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category_id);

-- Module discovery sessions (reuse pattern from goals)
CREATE TABLE IF NOT EXISTS module_discovery_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    module TEXT NOT NULL CHECK (module IN ('nutrition', 'exercise', 'finance')),
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    ended_at TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed', 'abandoned')),
    messages_json TEXT NOT NULL DEFAULT '[]',
    extracted_data_json TEXT DEFAULT '{}',
    context_snapshot TEXT,
    summary TEXT
);

CREATE INDEX IF NOT EXISTS idx_module_discovery_module ON module_discovery_sessions(module);

-- =============================================

CREATE TABLE IF NOT EXISTS self_profile_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- SECTION: Core Identity
    birth_date TEXT,
    birth_place TEXT,
    gender TEXT,
    nationality TEXT,
    ethnicities TEXT DEFAULT '[]',

    -- SECTION: Current Situation
    current_city TEXT,
    current_country TEXT,
    living_situation TEXT,
    years_at_location REAL,

    -- SECTION: Family Origins
    mother_alive INTEGER,
    mother_age INTEGER,
    mother_occupation TEXT,
    mother_relationship TEXT,
    father_alive INTEGER,
    father_age INTEGER,
    father_occupation TEXT,
    father_relationship TEXT,
    parents_status TEXT,
    childhood_structure TEXT,
    childhood_socioeconomic TEXT,
    childhood_location TEXT,
    num_siblings INTEGER,
    birth_order TEXT,
    siblings_json TEXT DEFAULT '[]',

    -- SECTION: Education
    highest_education TEXT,
    field_of_study TEXT,
    schools_json TEXT DEFAULT '[]',

    -- SECTION: Career
    current_occupation TEXT,
    current_industry TEXT,
    years_in_role REAL,
    career_satisfaction INTEGER,
    jobs_json TEXT DEFAULT '[]',

    -- SECTION: Relationships
    relationship_status TEXT,
    partner_name TEXT,
    relationship_years REAL,
    relationship_satisfaction INTEGER,
    has_children INTEGER,
    num_children INTEGER,
    children_json TEXT DEFAULT '[]',
    num_past_relationships INTEGER,
    longest_relationship_years REAL,
    age_first_relationship INTEGER,
    relationship_patterns_reflection TEXT,

    -- SECTION: Health
    height_cm REAL,
    weight_kg REAL,
    chronic_conditions_json TEXT DEFAULT '[]',
    medications_json TEXT DEFAULT '[]',
    allergies_json TEXT DEFAULT '[]',
    mental_health_history_json TEXT DEFAULT '[]',
    in_therapy INTEGER,
    attachment_style TEXT,

    -- SECTION: Values & Identity
    core_values_json TEXT DEFAULT '[]',
    religious_spiritual TEXT,
    religious_practice TEXT,
    native_language TEXT,
    languages_json TEXT DEFAULT '[]',
    mbti TEXT,
    big_five_json TEXT,

    -- SECTION: Life Story (McAdams)
    life_chapters_json TEXT DEFAULT '[]',
    life_theme TEXT,

    -- SECTION: Context & Preferences
    preferred_name TEXT,
    pronouns TEXT,
    timezone TEXT,
    communication_style TEXT,

    -- SECTION: Financial (optional)
    income_bracket TEXT,
    owns_home INTEGER,
    financial_stress INTEGER,

    -- Metadata
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    completeness_score REAL DEFAULT 0.0
);
"""


def init_db_sync():
    conn = sqlite3.connect(str(DB_PATH))
    conn.executescript(SCHEMA_SQL)
    _migrate_diary_columns(conn)
    _migrate_goals_columns(conn)
    _migrate_body_module(conn)
    _migrate_calendar_and_memory_module(conn)
    _seed_profile_domains(conn)
    _seed_life_domains(conn)
    _seed_expense_categories(conn)
    conn.commit()
    conn.close()


def _migrate_diary_columns(conn: sqlite3.Connection):
    cols = {row[1] for row in conn.execute("PRAGMA table_info(diary_entries)").fetchall()}
    if "duration_s" not in cols:
        conn.execute("ALTER TABLE diary_entries ADD COLUMN duration_s REAL")
    if "nash_response" not in cols:
        conn.execute("ALTER TABLE diary_entries ADD COLUMN nash_response TEXT")


def _migrate_goals_columns(conn: sqlite3.Connection):
    """Migrate goals schema to the typed life-graph structure."""
    goal_cols_info = conn.execute("PRAGMA table_info(goals)").fetchall()
    goal_cols = {row[1]: row for row in goal_cols_info}

    required_goal_columns = {
        "domain_id",
        "domain_tags_json",
        "parent_goal_id",
        "node_type",
        "title",
        "description",
        "why_matters",
        "horizon",
        "start_date",
        "target_date",
        "cadence_text",
        "time_cost_min",
        "energy_cost",
        "attention_cost",
        "status",
        "progress_pct",
        "motivation_type",
        "importance",
        "difficulty",
        "commitment",
        "specificity",
        "locus_of_control",
        "nash_opinion",
        "coherence_score",
        "conflicts_json",
        "synergies_json",
        "priority_rank",
        "source",
        "discovery_session_id",
        "created_at",
        "updated_at",
        "completed_at",
    }
    horizon_not_null = bool(goal_cols.get("horizon") and goal_cols["horizon"][3])
    needs_goal_rebuild = horizon_not_null or not required_goal_columns.issubset(set(goal_cols))

    if needs_goal_rebuild:
        _rebuild_goals_table(conn, set(goal_cols))

    session_cols = {row[1] for row in conn.execute("PRAGMA table_info(goal_discovery_sessions)").fetchall()}
    if "extracted_relations_json" not in session_cols:
        conn.execute("ALTER TABLE goal_discovery_sessions ADD COLUMN extracted_relations_json TEXT DEFAULT '[]'")
        conn.execute(
            "UPDATE goal_discovery_sessions SET extracted_relations_json = '[]' WHERE extracted_relations_json IS NULL"
        )

    relation_table_sql_row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'goal_relations'"
    ).fetchone()
    relation_table_sql = (relation_table_sql_row[0] or "") if relation_table_sql_row else ""
    needs_relation_rebuild = "drives" not in relation_table_sql or "reinforces" not in relation_table_sql or "costs" not in relation_table_sql
    if needs_relation_rebuild:
        _rebuild_goal_relations_table(conn)

    conn.execute("UPDATE goals SET start_date = date(created_at) WHERE start_date IS NULL")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_goals_parent ON goals(parent_goal_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_goals_node_type ON goals(node_type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_goal_relations_source ON goal_relations(source_goal_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_goal_relations_target ON goal_relations(target_goal_id)")


def _migrate_body_module(conn: sqlite3.Connection):
    profile_cols = {row[1] for row in conn.execute("PRAGMA table_info(exercise_profile)").fetchall()}
    profile_defaults = {
        "minimum_session_min": "INTEGER DEFAULT 12",
        "optimal_session_min": "INTEGER DEFAULT 45",
        "schedule_days_json": "TEXT DEFAULT '[]'",
        "barriers_json": "TEXT DEFAULT '[]'",
        "enjoyment_json": "TEXT DEFAULT '[]'",
        "preferred_location": "TEXT DEFAULT 'either' CHECK (preferred_location IN ('home', 'gym', 'either'))",
        "preferred_split": "TEXT DEFAULT 'auto' CHECK (preferred_split IN ('auto', 'full_body', 'upper_lower'))",
        "primary_goal": "TEXT DEFAULT 'muscle_gain' CHECK (primary_goal IN ('muscle_gain', 'strength', 'recomposition', 'general_fitness'))",
        "height_cm": "REAL",
        "training_history_notes": "TEXT",
    }
    for column, definition in profile_defaults.items():
        if column not in profile_cols:
            conn.execute(f"ALTER TABLE exercise_profile ADD COLUMN {column} {definition}")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS exercise_equipment_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location TEXT NOT NULL CHECK (location IN ('home', 'gym')),
            category TEXT NOT NULL,
            label TEXT NOT NULL,
            max_load_kg REAL,
            quantity INTEGER DEFAULT 1,
            notes TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_exercise_equipment_location ON exercise_equipment_items(location)")

    session_cols = {row[1] for row in conn.execute("PRAGMA table_info(workout_sessions)").fetchall()}
    session_defaults = {
        "focus_code": "TEXT",
        "planned_location": "TEXT CHECK (planned_location IN ('home', 'gym'))",
        "actual_location": "TEXT CHECK (actual_location IN ('home', 'gym'))",
        "duration_min": "INTEGER",
        "session_rpe": "INTEGER CHECK (session_rpe BETWEEN 1 AND 10)",
        "fallback_used": "INTEGER DEFAULT 0",
        "plan_source": "TEXT DEFAULT 'manual' CHECK (plan_source IN ('manual', 'generated', 'template'))",
    }
    for column, definition in session_defaults.items():
        if column not in session_cols:
            conn.execute(f"ALTER TABLE workout_sessions ADD COLUMN {column} {definition}")

    log_cols = {row[1] for row in conn.execute("PRAGMA table_info(exercise_logs)").fetchall()}
    log_defaults = {
        "movement_pattern": "TEXT",
        "equipment_context": "TEXT",
        "location": "TEXT CHECK (location IN ('home', 'gym'))",
        "volume_load": "REAL",
        "hard_sets": "INTEGER",
        "best_set_weight_kg": "REAL",
        "best_set_reps": "INTEGER",
    }
    for column, definition in log_defaults.items():
        if column not in log_cols:
            conn.execute(f"ALTER TABLE exercise_logs ADD COLUMN {column} {definition}")

    pr_cols = {row[1] for row in conn.execute("PRAGMA table_info(personal_records)").fetchall()}
    pr_defaults = {
        "metric_type": "TEXT DEFAULT 'estimated_1rm' CHECK (metric_type IN ('estimated_1rm', 'load_reps', 'repetition'))",
        "estimated_1rm": "REAL",
        "session_id": "INTEGER REFERENCES workout_sessions(id)",
        "notes": "TEXT",
    }
    for column, definition in pr_defaults.items():
        if column not in pr_cols:
            conn.execute(f"ALTER TABLE personal_records ADD COLUMN {column} {definition}")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS body_measurement_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            taken_on TEXT NOT NULL,
            weight_kg REAL,
            waist_cm REAL,
            hip_cm REAL,
            chest_cm REAL,
            arm_relaxed_cm REAL,
            arm_flexed_cm REAL,
            thigh_cm REAL,
            calf_cm REAL,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_body_measurements_taken_on ON body_measurement_snapshots(taken_on)")


def _migrate_calendar_and_memory_module(conn: sqlite3.Connection):
    """Add calendar orchestration and structured autobiographical memory fields."""
    memory_cols = {row[1] for row in conn.execute("PRAGMA table_info(memories)").fetchall()}
    memory_defaults = {
        "diary_entry_id": "INTEGER REFERENCES diary_entries(id)",
        "semantic_unit_id": "INTEGER REFERENCES semantic_units(id)",
        "title": "TEXT",
        "occurred_year_start": "INTEGER",
        "occurred_year_end": "INTEGER",
        "age_start": "INTEGER",
        "age_end": "INTEGER",
        "place_name": "TEXT",
        "people_json": "TEXT NOT NULL DEFAULT '[]'",
        "themes_json": "TEXT NOT NULL DEFAULT '[]'",
        "emotional_valence": "TEXT",
        "memory_type": "TEXT",
        "significance": "INTEGER CHECK (significance IS NULL OR significance BETWEEN 1 AND 5)",
        "sensory_details": "TEXT",
        "confidence": "REAL CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1)",
        "user_verified": "INTEGER NOT NULL DEFAULT 0",
        "notes": "TEXT",
        "updated_at": "TEXT",
    }
    for column, definition in memory_defaults.items():
        if column not in memory_cols:
            conn.execute(f"ALTER TABLE memories ADD COLUMN {column} {definition}")
    conn.execute("UPDATE memories SET updated_at = COALESCE(updated_at, timestamp)")
    conn.execute("UPDATE memories SET title = COALESCE(title, topic)")
    conn.execute("UPDATE memories SET people_json = COALESCE(people_json, '[]')")
    conn.execute("UPDATE memories SET themes_json = COALESCE(themes_json, '[]')")

    semantic_cols = {row[1] for row in conn.execute("PRAGMA table_info(semantic_units)").fetchall()}
    if "metadata_json" not in semantic_cols:
        conn.execute("ALTER TABLE semantic_units ADD COLUMN metadata_json TEXT NOT NULL DEFAULT '{}'")

    # Older databases do not see tables newly added to SCHEMA_SQL until this migration runs.
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS schedule_preferences (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            timezone TEXT NOT NULL DEFAULT 'America/Lima',
            day_start_time TEXT NOT NULL DEFAULT '08:00',
            day_end_time TEXT NOT NULL DEFAULT '23:00',
            focus_window_start TEXT DEFAULT '09:00',
            focus_window_end TEXT DEFAULT '13:00',
            default_task_duration_min INTEGER NOT NULL DEFAULT 30,
            transition_buffer_min INTEGER NOT NULL DEFAULT 10,
            max_scheduled_min_per_day INTEGER NOT NULL DEFAULT 480,
            preferred_work_days_json TEXT NOT NULL DEFAULT '[0,1,2,3,4]',
            protected_windows_json TEXT NOT NULL DEFAULT '[]',
            notes TEXT,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS schedule_inputs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            input_mode TEXT NOT NULL DEFAULT 'text' CHECK (input_mode IN ('text', 'audio', 'diary', 'engine')),
            raw_text TEXT NOT NULL,
            audio_path TEXT,
            command_type TEXT,
            interpretation_json TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'received' CHECK (status IN ('received', 'processed', 'needs_review', 'failed')),
            result_json TEXT NOT NULL DEFAULT '{}',
            processed_at TEXT
        );
        CREATE TABLE IF NOT EXISTS calendar_series (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            item_type TEXT NOT NULL DEFAULT 'routine' CHECK (item_type IN ('event', 'task', 'focus', 'routine', 'reminder')),
            recurrence_json TEXT NOT NULL,
            preferred_time TEXT,
            duration_min INTEGER NOT NULL DEFAULT 30 CHECK (duration_min > 0),
            first_date TEXT NOT NULL,
            until_date TEXT,
            source_kind TEXT NOT NULL DEFAULT 'direct',
            source_id INTEGER,
            source_key TEXT,
            goal_id INTEGER REFERENCES goals(id),
            domain_code TEXT,
            priority INTEGER NOT NULL DEFAULT 3 CHECK (priority BETWEEN 1 AND 5),
            flexibility TEXT NOT NULL DEFAULT 'movable' CHECK (flexibility IN ('fixed', 'movable', 'free')),
            energy_required INTEGER CHECK (energy_required IS NULL OR energy_required BETWEEN 1 AND 5),
            location TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS calendar_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            series_id INTEGER REFERENCES calendar_series(id),
            title TEXT NOT NULL,
            description TEXT,
            item_type TEXT NOT NULL DEFAULT 'task' CHECK (item_type IN ('event', 'task', 'focus', 'routine', 'reminder')),
            start_at TEXT,
            end_at TEXT,
            due_at TEXT,
            all_day INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'planned' CHECK (status IN ('planned', 'completed', 'skipped', 'cancelled')),
            source_kind TEXT NOT NULL DEFAULT 'direct',
            source_id INTEGER,
            source_key TEXT,
            goal_id INTEGER REFERENCES goals(id),
            domain_code TEXT,
            priority INTEGER NOT NULL DEFAULT 3 CHECK (priority BETWEEN 1 AND 5),
            flexibility TEXT NOT NULL DEFAULT 'movable' CHECK (flexibility IN ('fixed', 'movable', 'free')),
            energy_required INTEGER CHECK (energy_required IS NULL OR energy_required BETWEEN 1 AND 5),
            location TEXT,
            rationale TEXT,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            completed_at TEXT,
            UNIQUE(series_id, start_at)
        );
        CREATE TABLE IF NOT EXISTS calendar_suggestions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            resolved_at TEXT,
            status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
            proposal_type TEXT NOT NULL DEFAULT 'create_item' CHECK (proposal_type IN ('create_item', 'create_series', 'update_item', 'rearrange')),
            source_kind TEXT NOT NULL,
            source_id INTEGER,
            source_key TEXT,
            fingerprint TEXT NOT NULL UNIQUE,
            target_item_id INTEGER REFERENCES calendar_items(id),
            target_series_id INTEGER REFERENCES calendar_series(id),
            title TEXT NOT NULL,
            description TEXT,
            proposed_start_at TEXT,
            proposed_end_at TEXT,
            due_at TEXT,
            duration_min INTEGER,
            item_type TEXT NOT NULL DEFAULT 'task',
            recurrence_json TEXT,
            goal_id INTEGER REFERENCES goals(id),
            domain_code TEXT,
            priority INTEGER NOT NULL DEFAULT 3,
            flexibility TEXT NOT NULL DEFAULT 'movable',
            energy_required INTEGER,
            location TEXT,
            confidence REAL,
            rationale TEXT,
            payload_json TEXT NOT NULL DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS calendar_item_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL REFERENCES calendar_items(id),
            changed_at TEXT NOT NULL DEFAULT (datetime('now')),
            change_type TEXT NOT NULL,
            before_json TEXT NOT NULL DEFAULT '{}',
            after_json TEXT NOT NULL DEFAULT '{}',
            reason TEXT,
            schedule_input_id INTEGER REFERENCES schedule_inputs(id)
        );
        CREATE INDEX IF NOT EXISTS idx_calendar_items_start ON calendar_items(start_at);
        CREATE INDEX IF NOT EXISTS idx_calendar_items_status ON calendar_items(status);
        CREATE INDEX IF NOT EXISTS idx_calendar_items_source ON calendar_items(source_kind, source_id);
        CREATE INDEX IF NOT EXISTS idx_calendar_suggestions_status ON calendar_suggestions(status, created_at);
        CREATE INDEX IF NOT EXISTS idx_calendar_series_active ON calendar_series(active);
        CREATE INDEX IF NOT EXISTS idx_memories_year ON memories(occurred_year_start, occurred_year_end);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_memories_semantic_unit
            ON memories(semantic_unit_id) WHERE semantic_unit_id IS NOT NULL;
        """
    )
    conn.execute(
        """INSERT OR IGNORE INTO schedule_preferences (
               id, timezone, day_start_time, day_end_time, default_task_duration_min,
               transition_buffer_min, max_scheduled_min_per_day
        ) VALUES (1, 'America/Lima', '08:00', '23:00', 30, 10, 480)"""
    )
    _backfill_structured_memories(conn)


def _backfill_structured_memories(conn: sqlite3.Connection) -> None:
    """Promote previously extracted memory units into the chronological archive."""
    birth_year = None
    profile = conn.execute(
        "SELECT birth_date FROM self_profile_facts ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if profile and profile[0]:
        try:
            birth_year = datetime.strptime(profile[0], "%Y-%m-%d").year
        except ValueError:
            pass
    rows = conn.execute(
        """SELECT su.* FROM semantic_units su
           LEFT JOIN memories m ON m.semantic_unit_id = su.id
           WHERE su.unit_type = 'memory' AND m.id IS NULL"""
    ).fetchall()
    for row in rows:
        data = dict(zip([column[0] for column in conn.execute("SELECT * FROM semantic_units LIMIT 0").description], row))
        age = data.get("age_referenced")
        year_start = birth_year + int(age) if birth_year is not None and age is not None else None
        year_end = year_start + 1 if year_start is not None else None
        title = str(data.get("content") or "Recuerdo")[:100].strip()
        conn.execute(
            """INSERT OR IGNORE INTO memories (
                   topic, title, raw_transcript, life_period, semantic_unit_id,
                   occurred_year_start, occurred_year_end, age_start, age_end,
                   themes_json, emotional_valence, confidence, updated_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0.6, datetime('now'))""",
            (
                title,
                title,
                data.get("content") or title,
                data.get("life_period") or "unspecified",
                data.get("id"),
                year_start,
                year_end,
                age,
                age,
                data.get("topics") or "[]",
                data.get("emotional_valence"),
            ),
        )


def _rebuild_goals_table(conn: sqlite3.Connection, existing_cols: set[str]):
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("DROP TABLE IF EXISTS goals_rebuild")
    conn.execute(
        """
        CREATE TABLE goals_rebuild (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain_id INTEGER REFERENCES life_domains(id),
            domain_tags_json TEXT DEFAULT '[]',
            parent_goal_id INTEGER REFERENCES goals(id),
            node_type TEXT NOT NULL DEFAULT 'goal'
                CHECK (node_type IN ('identity', 'goal', 'system', 'action')),
            title TEXT NOT NULL,
            description TEXT,
            why_matters TEXT,
            horizon TEXT
                CHECK (horizon IS NULL OR horizon IN ('life', 'annual', 'quarterly', 'monthly', 'weekly')),
            start_date TEXT,
            target_date TEXT,
            cadence_text TEXT,
            time_cost_min INTEGER CHECK (time_cost_min IS NULL OR time_cost_min >= 0),
            energy_cost INTEGER CHECK (energy_cost IS NULL OR energy_cost BETWEEN 1 AND 5),
            attention_cost INTEGER CHECK (attention_cost IS NULL OR attention_cost BETWEEN 1 AND 5),
            status TEXT NOT NULL DEFAULT 'active'
                CHECK (status IN ('active', 'completed', 'abandoned', 'paused')),
            progress_pct INTEGER NOT NULL DEFAULT 0 CHECK (progress_pct BETWEEN 0 AND 100),
            motivation_type TEXT CHECK (motivation_type IN ('external', 'introjected', 'identified', 'intrinsic')),
            importance INTEGER CHECK (importance BETWEEN 1 AND 10),
            difficulty INTEGER CHECK (difficulty BETWEEN 1 AND 10),
            commitment INTEGER CHECK (commitment BETWEEN 1 AND 10),
            specificity INTEGER CHECK (specificity BETWEEN 1 AND 10),
            locus_of_control TEXT CHECK (locus_of_control IN ('internal', 'external', 'mixed')),
            nash_opinion TEXT,
            coherence_score REAL,
            conflicts_json TEXT DEFAULT '[]',
            synergies_json TEXT DEFAULT '[]',
            priority_rank INTEGER,
            source TEXT DEFAULT 'manual' CHECK (source IN ('manual', 'discovery')),
            discovery_session_id INTEGER REFERENCES goal_discovery_sessions(id),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            completed_at TEXT
        )
        """
    )

    def col(name: str, fallback_sql: str) -> str:
        return name if name in existing_cols else fallback_sql

    conn.execute(
        f"""
        INSERT INTO goals_rebuild (
            id, domain_id, domain_tags_json, parent_goal_id, node_type, title, description, why_matters,
            horizon, start_date, target_date, cadence_text, time_cost_min, energy_cost, attention_cost,
            status, progress_pct, motivation_type, importance, difficulty, commitment, specificity,
            locus_of_control, nash_opinion, coherence_score, conflicts_json, synergies_json, priority_rank,
            source, discovery_session_id, created_at, updated_at, completed_at
        )
        SELECT
            id,
            {col('domain_id', 'NULL')},
            COALESCE({col('domain_tags_json', "'[]'")}, '[]'),
            {col('parent_goal_id', 'NULL')},
            COALESCE({col('node_type', "'goal'")}, 'goal'),
            title,
            {col('description', 'NULL')},
            {col('why_matters', 'NULL')},
            {col('horizon', 'NULL')},
            {col('start_date', 'NULL')},
            {col('target_date', 'NULL')},
            {col('cadence_text', 'NULL')},
            {col('time_cost_min', 'NULL')},
            {col('energy_cost', 'NULL')},
            {col('attention_cost', 'NULL')},
            COALESCE({col('status', "'active'")}, 'active'),
            COALESCE({col('progress_pct', '0')}, 0),
            {col('motivation_type', 'NULL')},
            {col('importance', 'NULL')},
            {col('difficulty', 'NULL')},
            {col('commitment', 'NULL')},
            {col('specificity', 'NULL')},
            {col('locus_of_control', 'NULL')},
            {col('nash_opinion', 'NULL')},
            {col('coherence_score', 'NULL')},
            COALESCE({col('conflicts_json', "'[]'")}, '[]'),
            COALESCE({col('synergies_json', "'[]'")}, '[]'),
            {col('priority_rank', 'NULL')},
            COALESCE({col('source', "'manual'")}, 'manual'),
            {col('discovery_session_id', 'NULL')},
            COALESCE({col('created_at', "datetime('now')")}, datetime('now')),
            COALESCE({col('updated_at', "datetime('now')")}, datetime('now')),
            {col('completed_at', 'NULL')}
        FROM goals
        """
    )
    conn.execute("DROP TABLE goals")
    conn.execute("ALTER TABLE goals_rebuild RENAME TO goals")
    conn.execute("PRAGMA foreign_keys = ON")


def _rebuild_goal_relations_table(conn: sqlite3.Connection):
    existing = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'goal_relations'"
    ).fetchone()
    conn.execute("DROP TABLE IF EXISTS goal_relations_rebuild")
    conn.execute(
        """
        CREATE TABLE goal_relations_rebuild (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_goal_id INTEGER NOT NULL REFERENCES goals(id),
            target_goal_id INTEGER NOT NULL REFERENCES goals(id),
            relation_type TEXT NOT NULL DEFAULT 'related'
                CHECK (relation_type IN (
                    'related', 'supports', 'depends_on', 'conflicts_with', 'synergy', 'blocks',
                    'drives', 'requires', 'reinforces', 'costs'
                )),
            weight REAL,
            note TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(source_goal_id, target_goal_id, relation_type)
        )
        """
    )
    if existing:
        conn.execute(
            """
            INSERT INTO goal_relations_rebuild (
                id, source_goal_id, target_goal_id, relation_type, weight, note, created_at, updated_at
            )
            SELECT id, source_goal_id, target_goal_id, relation_type, weight, note, created_at, updated_at
            FROM goal_relations
            """
        )
        conn.execute("DROP TABLE goal_relations")
    conn.execute("ALTER TABLE goal_relations_rebuild RENAME TO goal_relations")


def _seed_profile_domains(conn: sqlite3.Connection):
    from backend.config import PROFILE_DOMAINS
    for domain in PROFILE_DOMAINS:
        conn.execute(
            "INSERT OR IGNORE INTO profile_summaries (domain, summary_text) VALUES (?, '')",
            (domain,),
        )


# Life domains based on Wheel of Life research
LIFE_DOMAINS_SEED = [
    ('career', 'Carrera', 'Trabajo, profesion, desarrollo profesional', '💼', '#3B82F6', 1),
    ('finance', 'Finanzas', 'Dinero, ahorro, estabilidad economica', '💰', '#10B981', 2),
    ('health', 'Salud', 'Salud fisica, ejercicio, nutricion, energia', '❤️', '#EF4444', 3),
    ('relationships', 'Relaciones', 'Pareja, familia, amigos, conexiones sociales', '👥', '#EC4899', 4),
    ('personal_growth', 'Crecimiento', 'Aprendizaje, habilidades, desarrollo personal', '🌱', '#8B5CF6', 5),
    ('fun_recreation', 'Diversion', 'Hobbies, ocio, tiempo libre, placer', '🎮', '#F59E0B', 6),
    ('environment', 'Entorno', 'Hogar, espacio fisico, orden', '🏠', '#6366F1', 7),
    ('contribution', 'Contribucion', 'Impacto, ayudar a otros, comunidad', '🤝', '#14B8A6', 8),
]


def _seed_life_domains(conn: sqlite3.Connection):
    """Seed the life_domains table with Wheel of Life domains."""
    for code, name_es, desc, icon, color, order in LIFE_DOMAINS_SEED:
        conn.execute(
            """INSERT OR IGNORE INTO life_domains (code, name_es, description_es, icon, color, sort_order)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (code, name_es, desc, icon, color, order),
        )


# Expense categories seed data
EXPENSE_CATEGORIES_SEED = [
    ('housing', 'Vivienda', '🏠', '#6366F1', 1, 1),
    ('food', 'Alimentacion', '🍽️', '#10B981', 0, 2),
    ('transport', 'Transporte', '🚗', '#F59E0B', 0, 3),
    ('health', 'Salud', '💊', '#EF4444', 0, 4),
    ('entertainment', 'Entretenimiento', '🎮', '#EC4899', 0, 5),
    ('education', 'Educacion', '📚', '#8B5CF6', 0, 6),
    ('debt', 'Deudas', '💳', '#DC2626', 1, 7),
    ('savings', 'Ahorro', '🏦', '#059669', 0, 8),
    ('personal', 'Personal', '👤', '#3B82F6', 0, 9),
    ('subscriptions', 'Suscripciones', '📱', '#7C3AED', 1, 10),
    ('other', 'Otros', '📦', '#6B7280', 0, 11),
]


def _seed_expense_categories(conn: sqlite3.Connection):
    """Seed the expense_categories table."""
    for code, name_es, icon, color, is_fixed, order in EXPENSE_CATEGORIES_SEED:
        conn.execute(
            """INSERT OR IGNORE INTO expense_categories (code, name_es, icon, color, is_fixed, sort_order)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (code, name_es, icon, color, is_fixed, order),
        )


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    return db


# --- Sync helpers for LangGraph tools (run in thread pool) ---

def _get_sync_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def insert_diary_entry(
    entry_type: str,
    raw_transcript: str,
    summary: str = "",
    domain_tags: str = "[]",
    energy_level: int | None = None,
    audio_path: str | None = None,
    duration_s: float | None = None,
) -> int:
    conn = _get_sync_conn()
    cursor = conn.execute(
        """INSERT INTO diary_entries (entry_type, raw_transcript, summary, domain_tags, energy_level, audio_path, duration_s)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (entry_type, raw_transcript, summary, domain_tags, energy_level, audio_path, duration_s),
    )
    entry_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return entry_id


def insert_memory(
    topic: str,
    raw_transcript: str,
    life_period: str = "unspecified",
    audio_path: str | None = None,
) -> int:
    conn = _get_sync_conn()
    cursor = conn.execute(
        """INSERT INTO memories (topic, raw_transcript, life_period, audio_path)
           VALUES (?, ?, ?, ?)""",
        (topic, raw_transcript, life_period, audio_path),
    )
    memory_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return memory_id


def insert_structured_memory(data: dict) -> dict:
    """Store a memory extracted from speech while preserving its source and uncertainty."""
    conn = _get_sync_conn()
    semantic_unit_id = data.get("semantic_unit_id")
    if semantic_unit_id is not None:
        existing = conn.execute(
            "SELECT * FROM memories WHERE semantic_unit_id = ?",
            (semantic_unit_id,),
        ).fetchone()
        if existing:
            conn.close()
            return _normalize_memory_row(existing)

    title = str(data.get("title") or data.get("topic") or "Recuerdo sin titulo").strip()
    raw_transcript = str(data.get("raw_transcript") or data.get("content") or title).strip()
    life_period = data.get("life_period") or "unspecified"
    if life_period not in {"childhood", "adolescence", "youth", "present", "unspecified"}:
        life_period = "unspecified"

    cursor = conn.execute(
        """INSERT INTO memories (
               topic, title, raw_transcript, life_period, audio_path, diary_entry_id,
               semantic_unit_id, occurred_year_start, occurred_year_end, age_start,
               age_end, place_name, people_json, themes_json, emotional_valence,
               memory_type, significance, sensory_details, confidence, user_verified,
               notes, updated_at
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
        (
            title,
            title,
            raw_transcript,
            life_period,
            data.get("audio_path"),
            data.get("diary_entry_id"),
            semantic_unit_id,
            data.get("occurred_year_start"),
            data.get("occurred_year_end"),
            data.get("age_start"),
            data.get("age_end"),
            data.get("place_name"),
            json.dumps(data.get("people") or [], ensure_ascii=False),
            json.dumps(data.get("themes") or [], ensure_ascii=False),
            data.get("emotional_valence"),
            data.get("memory_type"),
            data.get("significance"),
            data.get("sensory_details"),
            data.get("confidence"),
            1 if data.get("user_verified") else 0,
            data.get("notes"),
        ),
    )
    memory_id = int(cursor.lastrowid)
    conn.commit()
    row = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
    conn.close()
    return _normalize_memory_row(row)


def _normalize_memory_row(row: sqlite3.Row | dict) -> dict:
    result = dict(row)
    for raw_field, parsed_field in [("people_json", "people"), ("themes_json", "themes")]:
        try:
            result[parsed_field] = json.loads(result.get(raw_field) or "[]")
        except (TypeError, json.JSONDecodeError):
            result[parsed_field] = []
    return result


def get_memories(limit: int = 500, search: str | None = None) -> list[dict]:
    conn = _get_sync_conn()
    params: list = []
    where = ""
    if search and search.strip():
        needle = f"%{search.strip()}%"
        where = "WHERE title LIKE ? OR raw_transcript LIKE ? OR place_name LIKE ? OR themes_json LIKE ?"
        params.extend([needle, needle, needle, needle])
    params.append(max(1, min(int(limit), 2000)))
    rows = conn.execute(
        f"""SELECT * FROM memories {where}
            ORDER BY
                CASE WHEN occurred_year_end IS NULL THEN 1 ELSE 0 END,
                occurred_year_end DESC,
                occurred_year_start DESC,
                timestamp DESC
            LIMIT ?""",
        params,
    ).fetchall()
    conn.close()
    return [_normalize_memory_row(row) for row in rows]


def update_memory(memory_id: int, updates: dict) -> dict | None:
    allowed = {
        "title", "raw_transcript", "life_period", "occurred_year_start",
        "occurred_year_end", "age_start", "age_end", "place_name",
        "emotional_valence", "memory_type", "significance", "sensory_details",
        "confidence", "user_verified", "notes",
    }
    normalized = {key: value for key, value in updates.items() if key in allowed}
    if "people" in updates:
        normalized["people_json"] = json.dumps(updates.get("people") or [], ensure_ascii=False)
    if "themes" in updates:
        normalized["themes_json"] = json.dumps(updates.get("themes") or [], ensure_ascii=False)
    if not normalized:
        return None
    normalized["updated_at"] = datetime.now().isoformat(timespec="seconds")
    if "title" in normalized:
        normalized["topic"] = normalized["title"]
    conn = _get_sync_conn()
    assignments = ", ".join(f"{field} = ?" for field in normalized)
    conn.execute(
        f"UPDATE memories SET {assignments} WHERE id = ?",
        [*normalized.values(), memory_id],
    )
    conn.commit()
    row = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
    conn.close()
    return _normalize_memory_row(row) if row else None


def delete_memory(memory_id: int) -> bool:
    conn = _get_sync_conn()
    cursor = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted


def insert_profile_fact(
    domain: str,
    statement: str,
    fact_type: str = "declared",
    source_type: str = "diary",
) -> int:
    conn = _get_sync_conn()
    cursor = conn.execute(
        """INSERT INTO profile_facts (domain, statement, fact_type, source_type)
           VALUES (?, ?, ?, ?)""",
        (domain, statement, fact_type, source_type),
    )
    fact_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return fact_id


def get_recent_diary_entries(n: int = 5) -> list[dict]:
    conn = _get_sync_conn()
    rows = conn.execute(
        "SELECT * FROM diary_entries ORDER BY timestamp DESC LIMIT ?", (n,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_profile_summaries() -> dict[str, str]:
    conn = _get_sync_conn()
    rows = conn.execute("SELECT domain, summary_text FROM profile_summaries").fetchall()
    conn.close()
    return {r["domain"]: r["summary_text"] for r in rows}


def apply_profile_summary_updates(updates: dict[str, str]) -> int:
    """Persist new summary_text per domain. Empty string allowed."""
    from backend.config import PROFILE_DOMAINS

    conn = _get_sync_conn()
    n = 0
    for domain, text in updates.items():
        if domain not in PROFILE_DOMAINS:
            continue
        conn.execute(
            """UPDATE profile_summaries SET summary_text = ?, last_updated = datetime('now')
               WHERE domain = ?""",
            (text, domain),
        )
        n += 1
    conn.commit()
    conn.close()
    return n


def get_profile_facts(domain: str | None = None) -> list[dict]:
    conn = _get_sync_conn()
    if domain:
        rows = conn.execute(
            "SELECT * FROM profile_facts WHERE domain = ? ORDER BY weight DESC", (domain,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM profile_facts ORDER BY weight DESC"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_entry_count() -> int:
    conn = _get_sync_conn()
    count = conn.execute("SELECT COUNT(*) FROM diary_entries").fetchone()[0]
    conn.close()
    return count


def update_diary_nash_response(entry_id: int, nash_response: str) -> None:
    """Update a diary entry with Nash's response."""
    conn = _get_sync_conn()
    conn.execute(
        "UPDATE diary_entries SET nash_response = ? WHERE id = ?",
        (nash_response, entry_id),
    )
    conn.commit()
    conn.close()


def get_entries_without_response(limit: int = 50) -> list[dict]:
    """Get diary entries that don't have a Nash response yet."""
    conn = _get_sync_conn()
    rows = conn.execute(
        """SELECT id, raw_transcript FROM diary_entries
           WHERE nash_response IS NULL OR TRIM(nash_response) = ''
           ORDER BY id DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Diary Conversations helpers ---

MAX_CONVERSATION_MESSAGES = 11  # 1 initial + 5 user replies + 5 Nash replies


def get_diary_conversation(diary_entry_id: int) -> dict | None:
    """Get conversation for a diary entry."""
    conn = _get_sync_conn()
    row = conn.execute(
        "SELECT * FROM diary_conversations WHERE diary_entry_id = ?",
        (diary_entry_id,),
    ).fetchone()
    conn.close()
    if row:
        result = dict(row)
        import json
        result['messages'] = json.loads(result['messages_json'])
        return result
    return None


def add_conversation_message(
    diary_entry_id: int,
    role: str,  # 'user' or 'nash'
    content: str,
    audio_path: str | None = None,
) -> dict | None:
    """Add a message to a diary conversation. Returns updated conversation or None if limit reached."""
    import json

    conn = _get_sync_conn()

    # Get or create conversation
    row = conn.execute(
        "SELECT * FROM diary_conversations WHERE diary_entry_id = ?",
        (diary_entry_id,),
    ).fetchone()

    message = {'role': role, 'content': content}
    if audio_path:
        message['audio_path'] = audio_path

    if row:
        messages = json.loads(row['messages_json'])
        message_count = row['message_count']

        # Check limit
        if message_count >= MAX_CONVERSATION_MESSAGES:
            conn.close()
            return None

        messages.append(message)
        message_count += 1

        conn.execute(
            """UPDATE diary_conversations
               SET messages_json = ?, message_count = ?, updated_at = datetime('now')
               WHERE diary_entry_id = ?""",
            (json.dumps(messages), message_count, diary_entry_id),
        )
    else:
        messages = [message]
        message_count = 1
        conn.execute(
            """INSERT INTO diary_conversations (diary_entry_id, messages_json, message_count)
               VALUES (?, ?, ?)""",
            (diary_entry_id, json.dumps(messages), message_count),
        )

    conn.commit()
    conn.close()

    return {
        'diary_entry_id': diary_entry_id,
        'messages': messages,
        'message_count': message_count,
        'can_continue': message_count < MAX_CONVERSATION_MESSAGES,
    }


def get_conversation_context(diary_entry_id: int) -> str:
    """Build context string from original entry + conversation for agent."""
    conn = _get_sync_conn()

    # Get original entry
    entry = conn.execute(
        "SELECT raw_transcript, nash_response FROM diary_entries WHERE id = ?",
        (diary_entry_id,),
    ).fetchone()

    # Get conversation
    conv = conn.execute(
        "SELECT messages_json FROM diary_conversations WHERE diary_entry_id = ?",
        (diary_entry_id,),
    ).fetchone()

    conn.close()

    if not entry:
        return ""

    import json
    parts = [f"[Entrada original del usuario]: {entry['raw_transcript']}"]

    if entry['nash_response']:
        parts.append(f"[Tu respuesta inicial]: {entry['nash_response']}")

    if conv:
        messages = json.loads(conv['messages_json'])
        for msg in messages:
            role_label = "Usuario" if msg['role'] == 'user' else "Nash"
            parts.append(f"[{role_label}]: {msg['content']}")

    return "\n\n".join(parts)


def link_audio_if_transcript_matches(
    raw_transcript: str,
    audio_path: str,
    summary: str,
) -> bool:
    """If a diary row exists with the same transcript and no audio yet, attach file."""
    conn = _get_sync_conn()
    row = conn.execute(
        """SELECT id FROM diary_entries
           WHERE raw_transcript = ? AND (audio_path IS NULL OR TRIM(audio_path) = '')
           LIMIT 1""",
        (raw_transcript,),
    ).fetchone()
    if row:
        conn.execute(
            """UPDATE diary_entries SET audio_path = ?, summary = CASE
               WHEN summary IS NULL OR TRIM(summary) = '' THEN ?
               ELSE summary END
               WHERE id = ?""",
            (audio_path, summary, row[0]),
        )
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False


def get_registered_audio_basenames() -> set[str]:
    """Basenames of audio files already linked to a diary row."""
    from pathlib import Path

    conn = _get_sync_conn()
    rows = conn.execute(
        "SELECT audio_path FROM diary_entries WHERE audio_path IS NOT NULL AND TRIM(audio_path) != ''"
    ).fetchall()
    conn.close()
    out: set[str] = set()
    for r in rows:
        ap = r[0]
        if ap:
            out.add(Path(ap).name)
    return out


# --- Semantic Units helpers ---

def insert_semantic_unit(
    unit_type: str,
    content: str,
    diary_entry_id: int | None = None,
    life_period: str | None = None,
    age_referenced: int | None = None,
    topics: str = "[]",
    emotional_valence: str | None = None,
    domains: str = "[]",
    insight_potential: str = "low",
    chroma_id: str | None = None,
    metadata_json: str = "{}",
) -> int:
    conn = _get_sync_conn()
    cursor = conn.execute(
        """INSERT INTO semantic_units
           (diary_entry_id, unit_type, content, life_period, age_referenced,
            topics, emotional_valence, domains, insight_potential, chroma_id, metadata_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (diary_entry_id, unit_type, content, life_period, age_referenced,
         topics, emotional_valence, domains, insight_potential, chroma_id, metadata_json),
    )
    unit_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return unit_id


def update_semantic_unit_chroma_id(unit_id: int, chroma_id: str) -> None:
    conn = _get_sync_conn()
    conn.execute(
        "UPDATE semantic_units SET chroma_id = ? WHERE id = ?",
        (chroma_id, unit_id),
    )
    conn.commit()
    conn.close()


def get_semantic_units_by_diary_id(diary_entry_id: int) -> list[dict]:
    conn = _get_sync_conn()
    rows = conn.execute(
        "SELECT * FROM semantic_units WHERE diary_entry_id = ? ORDER BY id",
        (diary_entry_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_recent_semantic_units(n: int = 20) -> list[dict]:
    conn = _get_sync_conn()
    rows = conn.execute(
        "SELECT * FROM semantic_units ORDER BY timestamp DESC LIMIT ?", (n,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_semantic_units() -> list[dict]:
    conn = _get_sync_conn()
    rows = conn.execute(
        "SELECT * FROM semantic_units ORDER BY id"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Question Engine helpers ---

def insert_asked_question(
    question_text: str,
    question_type: str,
    framework: str,
    domains_targeted: str = "[]",
    why_asked: str | None = None,
) -> int:
    conn = _get_sync_conn()
    cursor = conn.execute(
        """INSERT INTO asked_questions
           (question_text, question_type, framework, domains_targeted, why_asked)
           VALUES (?, ?, ?, ?, ?)""",
        (question_text, question_type, framework, domains_targeted, why_asked),
    )
    question_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return question_id


def insert_question_answer(
    question_id: int,
    raw_transcript: str,
    semantic_units_extracted: str = "[]",
) -> int:
    conn = _get_sync_conn()
    cursor = conn.execute(
        """INSERT INTO daily_question_answers
           (question_id, raw_transcript, semantic_units_extracted)
           VALUES (?, ?, ?)""",
        (question_id, raw_transcript, semantic_units_extracted),
    )
    answer_id = cursor.lastrowid
    # Update the asked_question with the answer reference
    conn.execute(
        """UPDATE asked_questions
           SET answer_entry_id = ?, was_answered = 1
           WHERE id = ?""",
        (answer_id, question_id),
    )
    conn.commit()
    conn.close()
    return answer_id


def get_todays_questions() -> list[dict]:
    conn = _get_sync_conn()
    rows = conn.execute(
        """SELECT * FROM asked_questions
           WHERE date(timestamp) = date('now')
           ORDER BY id"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_questions_in_window(days: int = 30) -> list[dict]:
    conn = _get_sync_conn()
    rows = conn.execute(
        """SELECT question_text, question_type, domains_targeted
           FROM asked_questions
           WHERE timestamp >= datetime('now', ? || ' days')
           ORDER BY timestamp DESC""",
        (f"-{days}",),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_question_richness(question_id: int, score: float) -> None:
    conn = _get_sync_conn()
    conn.execute(
        "UPDATE asked_questions SET response_richness_score = ? WHERE id = ?",
        (score, question_id),
    )
    conn.commit()
    conn.close()


def get_question_stats() -> dict:
    """Get question effectiveness stats by type."""
    conn = _get_sync_conn()
    rows = conn.execute(
        """SELECT question_type,
                  COUNT(*) as total,
                  SUM(was_answered) as answered,
                  AVG(response_richness_score) as avg_richness
           FROM asked_questions
           GROUP BY question_type"""
    ).fetchall()
    conn.close()
    return {r["question_type"]: dict(r) for r in rows}


def get_last_emotional_valence() -> str | None:
    """Get the emotional valence from the most recent semantic unit with valence."""
    conn = _get_sync_conn()
    row = conn.execute(
        """SELECT emotional_valence FROM semantic_units
           WHERE emotional_valence IS NOT NULL
           ORDER BY timestamp DESC LIMIT 1"""
    ).fetchone()
    conn.close()
    return row["emotional_valence"] if row else None


# --- Self Profile Facts helpers ---

# Fields organized by section for completeness calculation
SELF_PROFILE_REQUIRED = [
    'birth_date', 'current_city', 'current_country', 'living_situation',
    'highest_education', 'current_occupation', 'relationship_status',
]

SELF_PROFILE_RECOMMENDED = [
    'mother_relationship', 'father_relationship', 'childhood_socioeconomic',
    'core_values_json', 'attachment_style', 'life_theme', 'preferred_name',
    'communication_style',
]

SELF_PROFILE_SECTIONS = {
    'identity': ['birth_date', 'birth_place', 'gender', 'nationality', 'ethnicities', 'preferred_name', 'pronouns'],
    'current': ['current_city', 'current_country', 'living_situation', 'years_at_location', 'timezone'],
    'family': ['mother_alive', 'mother_age', 'mother_occupation', 'mother_relationship',
               'father_alive', 'father_age', 'father_occupation', 'father_relationship',
               'parents_status', 'childhood_structure', 'childhood_socioeconomic',
               'childhood_location', 'num_siblings', 'birth_order', 'siblings_json'],
    'education': ['highest_education', 'field_of_study', 'schools_json'],
    'career': ['current_occupation', 'current_industry', 'years_in_role', 'career_satisfaction', 'jobs_json'],
    'relationships': ['relationship_status', 'partner_name', 'relationship_years', 'relationship_satisfaction',
                      'has_children', 'num_children', 'children_json', 'num_past_relationships',
                      'longest_relationship_years', 'age_first_relationship', 'relationship_patterns_reflection'],
    'health': ['height_cm', 'weight_kg', 'chronic_conditions_json', 'medications_json', 'allergies_json',
               'mental_health_history_json', 'in_therapy', 'attachment_style'],
    'values': ['core_values_json', 'religious_spiritual', 'religious_practice', 'native_language',
               'languages_json', 'mbti', 'big_five_json'],
    'life_story': ['life_chapters_json', 'life_theme'],
    'preferences': ['communication_style'],
    'financial': ['income_bracket', 'owns_home', 'financial_stress'],
}


def _calculate_completeness(profile: dict) -> float:
    """Calculate completeness score (0-1) based on required + recommended fields."""
    if not profile:
        return 0.0

    def is_filled(val):
        if val is None:
            return False
        if isinstance(val, str):
            if val.strip() == '' or val == '[]':
                return False
        return True

    required_filled = sum(1 for f in SELF_PROFILE_REQUIRED if is_filled(profile.get(f)))
    recommended_filled = sum(1 for f in SELF_PROFILE_RECOMMENDED if is_filled(profile.get(f)))

    required_weight = 0.6
    recommended_weight = 0.4

    required_score = (required_filled / len(SELF_PROFILE_REQUIRED)) * required_weight if SELF_PROFILE_REQUIRED else 0
    recommended_score = (recommended_filled / len(SELF_PROFILE_RECOMMENDED)) * recommended_weight if SELF_PROFILE_RECOMMENDED else 0

    return round(required_score + recommended_score, 3)


def _calculate_section_completeness(profile: dict) -> dict[str, float]:
    """Calculate completeness per section."""
    result = {}
    for section, fields in SELF_PROFILE_SECTIONS.items():
        filled = 0
        for f in fields:
            val = profile.get(f)
            if val is not None:
                if isinstance(val, str):
                    if val.strip() != '' and val != '[]':
                        filled += 1
                else:
                    filled += 1
        result[section] = round(filled / len(fields), 2) if fields else 0.0
    return result


def get_self_profile() -> dict | None:
    """Get the single self_profile_facts row (or None if not exists)."""
    conn = _get_sync_conn()
    row = conn.execute("SELECT * FROM self_profile_facts LIMIT 1").fetchone()
    conn.close()
    if row:
        profile = dict(row)
        profile['completeness_score'] = _calculate_completeness(profile)
        profile['section_completeness'] = _calculate_section_completeness(profile)
        return profile
    return None


def upsert_self_profile(updates: dict) -> dict:
    """Insert or update self_profile_facts. Returns the updated profile."""
    conn = _get_sync_conn()

    # Check if row exists
    existing = conn.execute("SELECT id FROM self_profile_facts LIMIT 1").fetchone()

    # Filter out metadata fields that shouldn't be updated directly
    filtered = {k: v for k, v in updates.items()
                if k not in ('id', 'created_at', 'updated_at', 'completeness_score', 'section_completeness')}

    if existing:
        # Update existing row
        if filtered:
            set_clause = ", ".join(f"{k} = ?" for k in filtered.keys())
            values = list(filtered.values())
            conn.execute(
                f"UPDATE self_profile_facts SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
                values + [existing[0]]
            )
    else:
        # Insert new row
        if filtered:
            cols = ", ".join(filtered.keys())
            placeholders = ", ".join("?" for _ in filtered)
            conn.execute(
                f"INSERT INTO self_profile_facts ({cols}) VALUES ({placeholders})",
                list(filtered.values())
            )
        else:
            # Insert empty row
            conn.execute("INSERT INTO self_profile_facts DEFAULT VALUES")

    conn.commit()
    conn.close()

    return get_self_profile() or {}


def get_unfilled_profile_fields() -> list[str]:
    """Get list of recommended fields that are not yet filled."""
    profile = get_self_profile()
    if not profile:
        return SELF_PROFILE_REQUIRED + SELF_PROFILE_RECOMMENDED

    unfilled = []
    for field in SELF_PROFILE_REQUIRED + SELF_PROFILE_RECOMMENDED:
        val = profile.get(field)
        if val is None or (isinstance(val, str) and (val.strip() == '' or val == '[]')):
            unfilled.append(field)
    return unfilled


# --- Life Domains & Goals helpers (Phase 3) ---

def get_life_domains() -> list[dict]:
    """Get all life domains ordered by sort_order."""
    conn = _get_sync_conn()
    rows = conn.execute(
        "SELECT * FROM life_domains ORDER BY sort_order"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_life_domain_by_code(code: str) -> dict | None:
    """Get a single domain by its code."""
    conn = _get_sync_conn()
    row = conn.execute(
        "SELECT * FROM life_domains WHERE code = ?", (code,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_latest_domain_ratings() -> dict[str, dict]:
    """Get the most recent rating for each domain.
    Returns {domain_code: {rating, notes, rated_at}}
    """
    conn = _get_sync_conn()
    # Get latest rating per domain using window function
    rows = conn.execute("""
        SELECT d.code, dr.rating, dr.notes, dr.rated_at
        FROM life_domains d
        LEFT JOIN (
            SELECT domain_id, rating, notes, rated_at,
                   ROW_NUMBER() OVER (PARTITION BY domain_id ORDER BY rated_at DESC) as rn
            FROM domain_ratings
        ) dr ON d.id = dr.domain_id AND dr.rn = 1
        ORDER BY d.sort_order
    """).fetchall()
    conn.close()
    return {
        r['code']: {
            'rating': r['rating'],
            'notes': r['notes'],
            'rated_at': r['rated_at']
        } for r in rows
    }


def get_domain_rating_history(domain_code: str, limit: int = 30) -> list[dict]:
    """Get rating history for a specific domain."""
    conn = _get_sync_conn()
    rows = conn.execute("""
        SELECT dr.rating, dr.notes, dr.rated_at
        FROM domain_ratings dr
        JOIN life_domains d ON d.id = dr.domain_id
        WHERE d.code = ?
        ORDER BY dr.rated_at DESC
        LIMIT ?
    """, (domain_code, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def insert_domain_rating(domain_code: str, rating: int, notes: str | None = None) -> int:
    """Insert a new rating for a domain. Returns the rating id."""
    conn = _get_sync_conn()
    # Get domain id
    domain = conn.execute(
        "SELECT id FROM life_domains WHERE code = ?", (domain_code,)
    ).fetchone()
    if not domain:
        conn.close()
        raise ValueError(f"Unknown domain: {domain_code}")

    cursor = conn.execute(
        "INSERT INTO domain_ratings (domain_id, rating, notes) VALUES (?, ?, ?)",
        (domain['id'], rating, notes),
    )
    rating_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return rating_id


def bulk_insert_domain_ratings(ratings: dict[str, int], notes: str | None = None) -> int:
    """Insert ratings for multiple domains at once. Returns count inserted."""
    conn = _get_sync_conn()
    count = 0
    for code, rating in ratings.items():
        domain = conn.execute(
            "SELECT id FROM life_domains WHERE code = ?", (code,)
        ).fetchone()
        if domain and 1 <= rating <= 10:
            conn.execute(
                "INSERT INTO domain_ratings (domain_id, rating, notes) VALUES (?, ?, ?)",
                (domain['id'], rating, notes),
            )
            count += 1
    conn.commit()
    conn.close()
    return count


# --- Goals CRUD ---

_KNOWN_DOMAIN_CODES = {
    "career",
    "finance",
    "health",
    "relationships",
    "personal_growth",
    "fun_recreation",
    "environment",
    "contribution",
}

GOAL_NODE_TYPES = {
    "identity",
    "goal",
    "system",
    "action",
}

GOAL_HORIZONS = {
    "life",
    "annual",
    "quarterly",
    "monthly",
    "weekly",
}

GOAL_HORIZON_ALIASES = {
    "vida": "life",
    "anual": "annual",
    "trimestral": "quarterly",
    "mensual": "monthly",
    "semanal": "weekly",
}

GOAL_RELATION_TYPES = {
    "related",
    "supports",
    "depends_on",
    "conflicts_with",
    "synergy",
    "blocks",
    "drives",
    "requires",
    "reinforces",
    "costs",
}

PARENT_CHILD_RULES: dict[str, set[str]] = {
    "identity": {"goal", "system"},
    "goal": {"goal", "system", "action"},
    "system": {"action"},
    "action": set(),
}

ACTION_COST_FIELDS = {
    "time_cost_min",
    "energy_cost",
    "attention_cost",
}


def _normalize_node_type(node_type: str | None) -> str:
    value = (node_type or "goal").strip().lower()
    if value not in GOAL_NODE_TYPES:
        raise ValueError(f"Tipo de nodo inválido: {node_type}")
    return value


def _normalize_horizon_value(horizon: str | None) -> str | None:
    if horizon is None:
        return None
    value = str(horizon).strip().lower()
    if not value:
        return None
    normalized = GOAL_HORIZON_ALIASES.get(value, value)
    if normalized not in GOAL_HORIZONS:
        raise ValueError(f"Horizonte inválido: {horizon}")
    return normalized


def _coerce_int_or_none(value) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValueError("Valor numérico inválido.")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Valor numérico inválido.") from exc


def _friendly_goal_integrity_error(exc: sqlite3.IntegrityError) -> str:
    message = str(exc)
    field_map = {
        "importance": "Importancia",
        "difficulty": "Dificultad",
        "commitment": "Compromiso",
        "specificity": "Especificidad",
        "energy_cost": "Costo de energía",
        "attention_cost": "Costo de atención",
        "time_cost_min": "Costo de tiempo",
        "progress_pct": "Progreso",
        "motivation_type": "Motivación",
        "horizon": "Horizonte",
    }
    for key, label in field_map.items():
        if key in message:
            return f"{label} tiene un valor inválido."
    return "Uno o más campos del nodo tienen un valor inválido."


def _normalize_goal_fields_for_node_type(
    node_type: str,
    horizon: str | None,
    cadence_text: str | None,
    time_cost_min,
    energy_cost,
    attention_cost,
) -> dict:
    normalized_horizon = _normalize_horizon_value(horizon)
    normalized_cadence = (cadence_text or "").strip() or None
    normalized_time_cost = _coerce_int_or_none(time_cost_min)
    normalized_energy_cost = _coerce_int_or_none(energy_cost)
    normalized_attention_cost = _coerce_int_or_none(attention_cost)

    if node_type == "goal":
        if normalized_horizon is None:
            raise ValueError("Los nodos de tipo goal requieren un horizonte.")
    elif node_type == "system":
        # Optional horizon for systems.
        pass
    else:
        normalized_horizon = None

    if node_type != "system":
        normalized_cadence = None

    if node_type != "action":
        normalized_time_cost = None
        normalized_energy_cost = None
        normalized_attention_cost = None

    if normalized_energy_cost is not None and not 1 <= normalized_energy_cost <= 5:
        raise ValueError("energy_cost debe estar entre 1 y 5.")
    if normalized_attention_cost is not None and not 1 <= normalized_attention_cost <= 5:
        raise ValueError("attention_cost debe estar entre 1 y 5.")
    if normalized_time_cost is not None and normalized_time_cost < 0:
        raise ValueError("time_cost_min no puede ser negativo.")

    return {
        "horizon": normalized_horizon,
        "cadence_text": normalized_cadence,
        "time_cost_min": normalized_time_cost,
        "energy_cost": normalized_energy_cost,
        "attention_cost": normalized_attention_cost,
    }


def _validate_parent_child_types(parent_type: str, child_type: str):
    allowed_children = PARENT_CHILD_RULES.get(parent_type, set())
    if child_type not in allowed_children:
        raise ValueError(
            f"Jerarquía inválida: un nodo {parent_type} no puede tener como hijo un nodo {child_type}."
        )


def _get_goal_row_for_validation(conn: sqlite3.Connection, goal_id: int):
    return conn.execute(
        "SELECT id, title, node_type FROM goals WHERE id = ?",
        (goal_id,),
    ).fetchone()


def _validate_parent_assignment(conn: sqlite3.Connection, child_goal_id: int | None, child_type: str, parent_goal_id: int | None):
    if parent_goal_id is None:
        return
    if child_goal_id is not None and parent_goal_id == child_goal_id:
        raise ValueError("Un nodo no puede ser su propio padre.")

    parent = _get_goal_row_for_validation(conn, parent_goal_id)
    if not parent:
        raise ValueError("Nodo padre no encontrado.")

    _validate_parent_child_types(parent["node_type"], child_type)


def _validate_existing_children_for_parent_type(conn: sqlite3.Connection, goal_id: int, parent_type: str):
    children = conn.execute(
        "SELECT id, node_type FROM goals WHERE parent_goal_id = ?",
        (goal_id,),
    ).fetchall()
    for child in children:
        _validate_parent_child_types(parent_type, child["node_type"])


def _coerce_domain_tags(domain_tags: list[str] | str | None) -> list[str]:
    """Normalize multi-domain tags (supports list, pipe/comma string, or None)."""
    if domain_tags is None:
        return []

    if isinstance(domain_tags, str):
        parts = [part.strip().lower() for part in domain_tags.replace(",", "|").split("|")]
        return [part for part in parts if part]

    if isinstance(domain_tags, list):
        normalized: list[str] = []
        for item in domain_tags:
            text = str(item).strip().lower()
            if text:
                normalized.append(text)
        return normalized

    return []


def _normalize_goal_row(row: sqlite3.Row | dict) -> dict:
    """Return API-friendly goal dict with parsed domain_tags list."""
    goal = dict(row)
    goal["node_type"] = _normalize_node_type(goal.get("node_type"))
    raw_tags = goal.get("domain_tags_json")
    tags: list[str] = []
    if isinstance(raw_tags, str) and raw_tags.strip():
        try:
            parsed = json.loads(raw_tags)
            if isinstance(parsed, list):
                tags = [str(item).strip().lower() for item in parsed if str(item).strip()]
        except Exception:
            tags = _coerce_domain_tags(raw_tags)
    goal["domain_tags"] = tags
    if "domain_tags_json" not in goal:
        goal["domain_tags_json"] = json.dumps(tags, ensure_ascii=False)
    if goal["node_type"] in {"identity", "action"}:
        goal["horizon"] = None
    if goal["node_type"] != "system":
        goal["cadence_text"] = None
    if goal["node_type"] != "action":
        goal["time_cost_min"] = None
        goal["energy_cost"] = None
        goal["attention_cost"] = None
    return goal

def get_goals(
    status: str | None = None,
    domain_code: str | None = None,
    horizon: str | None = None,
    node_type: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """Get goals with optional filters."""
    conn = _get_sync_conn()

    query = """
        SELECT g.*, d.code as domain_code, d.name_es as domain_name, d.icon as domain_icon
        FROM goals g
        LEFT JOIN life_domains d ON d.id = g.domain_id
        WHERE 1=1
    """
    params: list = []

    if status:
        query += " AND g.status = ?"
        params.append(status)
    if domain_code:
        query += " AND d.code = ?"
        params.append(domain_code)
    if horizon:
        query += " AND g.horizon = ?"
        params.append(horizon)
    if node_type:
        query += " AND g.node_type = ?"
        params.append(_normalize_node_type(node_type))

    query += " ORDER BY g.created_at DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [_normalize_goal_row(r) for r in rows]


def get_goal_by_id(goal_id: int) -> dict | None:
    """Get a single goal by id."""
    conn = _get_sync_conn()
    row = conn.execute("""
        SELECT g.*, d.code as domain_code, d.name_es as domain_name, d.icon as domain_icon
        FROM goals g
        LEFT JOIN life_domains d ON d.id = g.domain_id
        WHERE g.id = ?
    """, (goal_id,)).fetchone()
    conn.close()
    return _normalize_goal_row(row) if row else None


def insert_goal(
    title: str,
    domain_code: str | None = None,
    domain_tags: list[str] | str | None = None,
    parent_goal_id: int | None = None,
    node_type: str = 'goal',
    description: str | None = None,
    why_matters: str | None = None,
    horizon: str | None = 'quarterly',
    start_date: str | None = None,
    target_date: str | None = None,
    cadence_text: str | None = None,
    time_cost_min: int | None = None,
    energy_cost: int | None = None,
    attention_cost: int | None = None,
    motivation_type: str | None = None,
    # New discovery fields
    importance: int | None = None,
    difficulty: int | None = None,
    commitment: int | None = None,
    specificity: int | None = None,
    locus_of_control: str | None = None,
    nash_opinion: str | None = None,
    coherence_score: float | None = None,
    conflicts_json: str | None = None,
    synergies_json: str | None = None,
    priority_rank: int | None = None,
    source: str = 'manual',
    discovery_session_id: int | None = None,
) -> int:
    """Insert a new goal. Returns the goal id."""
    conn = _get_sync_conn()
    try:
        node_type = _normalize_node_type(node_type)

        normalized_tags = _coerce_domain_tags(domain_tags)
        if domain_code:
            domain_code = str(domain_code).strip().lower()
        if domain_code and domain_code not in normalized_tags:
            normalized_tags.insert(0, domain_code)

        # If primary domain isn't provided but tags include one known life-domain, use it.
        if not domain_code:
            domain_code = next((tag for tag in normalized_tags if tag in _KNOWN_DOMAIN_CODES), None)

        domain_id = None
        if domain_code:
            domain = conn.execute(
                "SELECT id FROM life_domains WHERE code = ?", (domain_code,)
            ).fetchone()
            if domain:
                domain_id = domain['id']

        normalized_fields = _normalize_goal_fields_for_node_type(
            node_type=node_type,
            horizon=horizon,
            cadence_text=cadence_text,
            time_cost_min=time_cost_min,
            energy_cost=energy_cost,
            attention_cost=attention_cost,
        )
        _validate_parent_assignment(conn, None, node_type, parent_goal_id)

        try:
            cursor = conn.execute("""
                INSERT INTO goals (
                    domain_id, domain_tags_json, parent_goal_id, node_type, title, description, why_matters,
                    horizon, start_date, target_date, cadence_text, time_cost_min, energy_cost, attention_cost, motivation_type,
                    importance, difficulty, commitment, specificity, locus_of_control,
                    nash_opinion, coherence_score, conflicts_json, synergies_json, priority_rank,
                    source, discovery_session_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                domain_id, json.dumps(normalized_tags, ensure_ascii=False), parent_goal_id, node_type, title, description, why_matters,
                normalized_fields['horizon'], start_date, target_date, normalized_fields['cadence_text'],
                normalized_fields['time_cost_min'], normalized_fields['energy_cost'], normalized_fields['attention_cost'], motivation_type,
                importance, difficulty, commitment, specificity, locus_of_control,
                nash_opinion, coherence_score, conflicts_json or '[]', synergies_json or '[]', priority_rank,
                source, discovery_session_id
            ))
        except sqlite3.IntegrityError as exc:
            raise ValueError(_friendly_goal_integrity_error(exc)) from exc

        goal_id = cursor.lastrowid
        conn.commit()
        return goal_id
    finally:
        conn.close()


def update_goal(goal_id: int, updates: dict) -> dict | None:
    """Update a goal. Returns updated goal or None if not found."""
    conn = _get_sync_conn()
    try:
        # Check if goal exists
        existing = conn.execute(
            """
            SELECT id, domain_tags_json, node_type, horizon, cadence_text,
                   time_cost_min, energy_cost, attention_cost
            FROM goals WHERE id = ?
            """,
            (goal_id,),
        ).fetchone()
        if not existing:
            return None

        # Handle domain_code -> domain_id conversion
        domain_code_input = None
        if 'domain_code' in updates:
            domain_code = updates.pop('domain_code')
            if domain_code:
                domain_code = str(domain_code).strip().lower()
                domain_code_input = domain_code
                domain = conn.execute(
                    "SELECT id FROM life_domains WHERE code = ?", (domain_code,)
                ).fetchone()
                updates['domain_id'] = domain['id'] if domain else None
            else:
                updates['domain_id'] = None

        if 'domain_tags' in updates:
            domain_tags_json = json.dumps(_coerce_domain_tags(updates.pop('domain_tags')), ensure_ascii=False)
            updates['domain_tags_json'] = domain_tags_json
        elif domain_code_input:
            existing_tags = _coerce_domain_tags(existing['domain_tags_json'] or "[]")
            if domain_code_input not in existing_tags:
                existing_tags.insert(0, domain_code_input)
            updates['domain_tags_json'] = json.dumps(existing_tags, ensure_ascii=False)

        # Filter allowed fields
        allowed = {
            'domain_id', 'domain_tags_json', 'parent_goal_id', 'node_type', 'title', 'description', 'why_matters', 'horizon',
            'start_date', 'target_date', 'cadence_text', 'time_cost_min', 'energy_cost', 'attention_cost',
            'status', 'progress_pct', 'motivation_type',
            # New discovery fields
            'importance', 'difficulty', 'commitment', 'specificity', 'locus_of_control',
            'nash_opinion', 'coherence_score', 'conflicts_json', 'synergies_json',
            'priority_rank', 'source', 'discovery_session_id'
        }
        filtered = {k: v for k, v in updates.items() if k in allowed}

        if not filtered:
            return get_goal_by_id(goal_id)

        target_node_type = _normalize_node_type(filtered.get('node_type', existing['node_type']))
        normalized_fields = _normalize_goal_fields_for_node_type(
            node_type=target_node_type,
            horizon=filtered.get('horizon', existing['horizon']),
            cadence_text=filtered.get('cadence_text', existing['cadence_text']),
            time_cost_min=filtered.get('time_cost_min', existing['time_cost_min']),
            energy_cost=filtered.get('energy_cost', existing['energy_cost']),
            attention_cost=filtered.get('attention_cost', existing['attention_cost']),
        )
        filtered['node_type'] = target_node_type
        filtered['horizon'] = normalized_fields['horizon']
        filtered['cadence_text'] = normalized_fields['cadence_text']
        filtered['time_cost_min'] = normalized_fields['time_cost_min']
        filtered['energy_cost'] = normalized_fields['energy_cost']
        filtered['attention_cost'] = normalized_fields['attention_cost']

        parent_goal_id = filtered.get('parent_goal_id', None)
        if 'parent_goal_id' not in filtered:
            current_parent = conn.execute(
                "SELECT parent_goal_id FROM goals WHERE id = ?",
                (goal_id,),
            ).fetchone()
            parent_goal_id = current_parent['parent_goal_id'] if current_parent else None
        _validate_parent_assignment(conn, goal_id, target_node_type, parent_goal_id)
        _validate_existing_children_for_parent_type(conn, goal_id, target_node_type)

        # Handle status change to completed
        if filtered.get('status') == 'completed':
            filtered['completed_at'] = "datetime('now')"

        set_parts = []
        values = []
        for k, v in filtered.items():
            if k == 'completed_at' and v == "datetime('now')":
                set_parts.append(f"{k} = datetime('now')")
            else:
                set_parts.append(f"{k} = ?")
                values.append(v)

        set_parts.append("updated_at = datetime('now')")
        values.append(goal_id)

        try:
            conn.execute(
                f"UPDATE goals SET {', '.join(set_parts)} WHERE id = ?",
                values
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError(_friendly_goal_integrity_error(exc)) from exc
        conn.commit()
    finally:
        conn.close()

    return get_goal_by_id(goal_id)


def delete_goal(goal_id: int) -> bool:
    """Delete a goal. Returns True if deleted."""
    conn = _get_sync_conn()
    conn.execute(
        "DELETE FROM goal_relations WHERE source_goal_id = ? OR target_goal_id = ?",
        (goal_id, goal_id),
    )
    conn.execute(
        "UPDATE goals SET parent_goal_id = NULL WHERE parent_goal_id = ?",
        (goal_id,),
    )
    cursor = conn.execute("DELETE FROM goals WHERE id = ?", (goal_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def get_goals_summary() -> dict:
    """Get summary stats for goals."""
    conn = _get_sync_conn()

    total = conn.execute("SELECT COUNT(*) FROM goals").fetchone()[0]
    active = conn.execute("SELECT COUNT(*) FROM goals WHERE status = 'active'").fetchone()[0]
    completed = conn.execute("SELECT COUNT(*) FROM goals WHERE status = 'completed'").fetchone()[0]

    by_horizon = {}
    rows = conn.execute("""
        SELECT horizon, COUNT(*) as count
        FROM goals WHERE status = 'active' AND horizon IS NOT NULL
        GROUP BY horizon
    """).fetchall()
    for r in rows:
        by_horizon[r['horizon']] = r['count']

    by_node_type = {}
    rows = conn.execute("""
        SELECT node_type, COUNT(*) as count
        FROM goals
        GROUP BY node_type
    """).fetchall()
    for r in rows:
        by_node_type[r['node_type']] = r['count']

    by_domain = {}
    rows = conn.execute("""
        SELECT d.code, d.name_es, COUNT(g.id) as count
        FROM life_domains d
        LEFT JOIN goals g ON g.domain_id = d.id AND g.status = 'active'
        GROUP BY d.id
        ORDER BY d.sort_order
    """).fetchall()
    for r in rows:
        by_domain[r['code']] = {'name': r['name_es'], 'count': r['count']}

    conn.close()
    return {
        'total': total,
        'active': active,
        'completed': completed,
        'by_horizon': by_horizon,
        'by_domain': by_domain,
        'by_node_type': by_node_type,
    }


def get_goals_graph(status: str | None = None) -> dict:
    """Return goal graph data as nodes + edges (hierarchy + relations)."""
    conn = _get_sync_conn()

    base_query = """
        SELECT g.*, d.code as domain_code, d.name_es as domain_name, d.icon as domain_icon
        FROM goals g
        LEFT JOIN life_domains d ON d.id = g.domain_id
        WHERE 1=1
    """
    params: list = []

    if status and status != 'all':
        base_query += " AND g.status = ?"
        params.append(status)
    elif status != 'all':
        # Default graph view: hide abandoned goals.
        base_query += " AND g.status != 'abandoned'"

    base_query += " ORDER BY g.created_at DESC"
    node_rows = conn.execute(base_query, params).fetchall()
    nodes = [_normalize_goal_row(r) for r in node_rows]
    node_ids = {n['id'] for n in nodes}

    edges: list[dict] = []

    # Hierarchy edges from parent_goal_id
    for node in nodes:
        parent_id = node.get('parent_goal_id')
        if parent_id and parent_id in node_ids:
            edges.append(
                {
                    'id': f"parent-{parent_id}-{node['id']}",
                    'source_goal_id': parent_id,
                    'target_goal_id': node['id'],
                    'relation_type': 'parent_child',
                    'kind': 'parent',
                    'relation_id': None,
                    'note': None,
                    'weight': None,
                }
            )

    # Explicit relation edges
    relation_rows = conn.execute(
        """
        SELECT id, source_goal_id, target_goal_id, relation_type, note, weight
        FROM goal_relations
        ORDER BY created_at DESC
        """
    ).fetchall()

    for row in relation_rows:
        rel = dict(row)
        if rel['source_goal_id'] not in node_ids or rel['target_goal_id'] not in node_ids:
            continue
        edges.append(
            {
                'id': f"relation-{rel['id']}",
                'source_goal_id': rel['source_goal_id'],
                'target_goal_id': rel['target_goal_id'],
                'relation_type': rel['relation_type'],
                'kind': 'relation',
                'relation_id': rel['id'],
                'note': rel.get('note'),
                'weight': rel.get('weight'),
            }
        )

    conn.close()
    return {
        'nodes': nodes,
        'edges': edges,
    }


def insert_goal_relation(
    source_goal_id: int,
    target_goal_id: int,
    relation_type: str = 'related',
    note: str | None = None,
    weight: float | None = None,
) -> dict:
    """Create a directed relation between two goals."""
    relation_type = (relation_type or 'related').strip().lower()
    if relation_type not in GOAL_RELATION_TYPES:
        raise ValueError(f"Tipo de relación inválido: {relation_type}")
    if source_goal_id == target_goal_id:
        raise ValueError("Una meta no puede relacionarse consigo misma.")

    conn = _get_sync_conn()

    source = conn.execute("SELECT id FROM goals WHERE id = ?", (source_goal_id,)).fetchone()
    target = conn.execute("SELECT id FROM goals WHERE id = ?", (target_goal_id,)).fetchone()
    if not source or not target:
        conn.close()
        raise ValueError("No se encontró una de las metas para crear la relación.")

    relation_id: int | None = None
    try:
        cursor = conn.execute(
            """
            INSERT INTO goal_relations (source_goal_id, target_goal_id, relation_type, note, weight)
            VALUES (?, ?, ?, ?, ?)
            """,
            (source_goal_id, target_goal_id, relation_type, note, weight),
        )
        relation_id = cursor.lastrowid
        conn.commit()
    except sqlite3.IntegrityError:
        existing = conn.execute(
            """
            SELECT * FROM goal_relations
            WHERE source_goal_id = ? AND target_goal_id = ? AND relation_type = ?
            """,
            (source_goal_id, target_goal_id, relation_type),
        ).fetchone()
        if existing:
            relation_id = existing['id']
        else:
            conn.close()
            raise

    row = conn.execute("SELECT * FROM goal_relations WHERE id = ?", (relation_id,)).fetchone()
    conn.close()
    if not row:
        raise ValueError("No se pudo crear la relación.")
    return dict(row)


def delete_goal_relation(relation_id: int) -> bool:
    """Delete a goal relation edge by id."""
    conn = _get_sync_conn()
    cursor = conn.execute("DELETE FROM goal_relations WHERE id = ?", (relation_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


# --- Goal Discovery Sessions helpers ---

def create_discovery_session(context_snapshot: str | None = None) -> int:
    """Create a new goal discovery session. Returns session id."""
    conn = _get_sync_conn()
    cursor = conn.execute(
        """INSERT INTO goal_discovery_sessions (context_snapshot)
           VALUES (?)""",
        (context_snapshot,)
    )
    session_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return session_id


def get_discovery_session(session_id: int) -> dict | None:
    """Get a discovery session by id."""
    import json
    conn = _get_sync_conn()
    row = conn.execute(
        "SELECT * FROM goal_discovery_sessions WHERE id = ?",
        (session_id,)
    ).fetchone()
    conn.close()

    if not row:
        return None

    result = dict(row)
    result['messages'] = json.loads(result['messages_json'])
    result['extracted_goals'] = json.loads(result['extracted_goals_json'])
    raw_relations = result.get('extracted_relations_json') or '[]'
    result['extracted_relations'] = json.loads(raw_relations)
    return result


def get_active_discovery_session() -> dict | None:
    """Get the current active discovery session (if any)."""
    import json
    conn = _get_sync_conn()
    row = conn.execute(
        """SELECT * FROM goal_discovery_sessions
           WHERE status = 'active'
           ORDER BY started_at DESC LIMIT 1"""
    ).fetchone()
    conn.close()

    if not row:
        return None

    result = dict(row)
    result['messages'] = json.loads(result['messages_json'])
    result['extracted_goals'] = json.loads(result['extracted_goals_json'])
    raw_relations = result.get('extracted_relations_json') or '[]'
    result['extracted_relations'] = json.loads(raw_relations)
    return result


def add_discovery_message(session_id: int, role: str, content: str) -> dict | None:
    """Add a message to a discovery session. Returns updated session."""
    import json
    from datetime import datetime

    conn = _get_sync_conn()
    row = conn.execute(
        "SELECT * FROM goal_discovery_sessions WHERE id = ?",
        (session_id,)
    ).fetchone()

    if not row:
        conn.close()
        return None

    messages = json.loads(row['messages_json'])
    messages.append({
        'role': role,
        'content': content,
        'timestamp': datetime.now().isoformat()
    })

    conn.execute(
        """UPDATE goal_discovery_sessions
           SET messages_json = ?
           WHERE id = ?""",
        (json.dumps(messages), session_id)
    )
    conn.commit()
    conn.close()

    return get_discovery_session(session_id)


def update_discovery_session(
    session_id: int,
    status: str | None = None,
    current_state: str | None = None,
    extracted_goals_json: str | None = None,
    extracted_relations_json: str | None = None,
    goals_confirmed: int | None = None,
    summary: str | None = None,
) -> dict | None:
    """Update a discovery session. Returns updated session."""
    conn = _get_sync_conn()

    updates = []
    values = []

    if status is not None:
        updates.append("status = ?")
        values.append(status)
        if status in ('completed', 'abandoned'):
            updates.append("ended_at = datetime('now')")

    if current_state is not None:
        updates.append("current_state = ?")
        values.append(current_state)

    if extracted_goals_json is not None:
        updates.append("extracted_goals_json = ?")
        values.append(extracted_goals_json)

    if extracted_relations_json is not None:
        updates.append("extracted_relations_json = ?")
        values.append(extracted_relations_json)

    if goals_confirmed is not None:
        updates.append("goals_confirmed = ?")
        values.append(goals_confirmed)

    if summary is not None:
        updates.append("summary = ?")
        values.append(summary)

    if not updates:
        conn.close()
        return get_discovery_session(session_id)

    values.append(session_id)
    conn.execute(
        f"UPDATE goal_discovery_sessions SET {', '.join(updates)} WHERE id = ?",
        values
    )
    conn.commit()
    conn.close()

    return get_discovery_session(session_id)


def get_goals_for_context() -> str:
    """Get all goals formatted for context injection."""
    goals = get_goals(status='active', limit=50)
    if not goals:
        return "No hay metas registradas todavía."

    lines = []
    for g in goals:
        domain = g.get('domain_name', 'Sin dominio')
        node_type = g.get('node_type', 'goal')
        horizon = g.get('horizon') or 'sin horizonte'
        progress = g.get('progress_pct', 0)
        why = g.get('why_matters', '')
        cadence = g.get('cadence_text')

        line = f"- [{domain}] [{node_type}] {g['title']} ({horizon}, {progress}% progreso)"
        if cadence:
            line += f"\n  Cadencia: {cadence}"
        if why:
            line += f"\n  Por qué importa: {why[:100]}"
        if g.get('nash_opinion'):
            line += f"\n  Mi opinión: {g['nash_opinion'][:100]}"
        lines.append(line)

    return "\n".join(lines)


def get_domain_ratings_for_context() -> str:
    """Get domain ratings formatted for context injection."""
    ratings = get_latest_domain_ratings()
    domains = get_life_domains()

    lines = []
    for d in domains:
        code = d['code']
        name = d['name_es']
        icon = d.get('icon', '')
        rating_info = ratings.get(code, {})
        rating = rating_info.get('rating')

        if rating:
            lines.append(f"- {icon} {name}: {rating}/10")
        else:
            lines.append(f"- {icon} {name}: Sin calificar")

    return "\n".join(lines)


# =============================================
# Module Discovery Sessions (Nutrition, Exercise, Finance)
# =============================================

def create_module_discovery_session(module: str, context_snapshot: str | None = None) -> int:
    """Create a new module discovery session. Returns session id."""
    conn = _get_sync_conn()
    cursor = conn.execute(
        """INSERT INTO module_discovery_sessions (module, context_snapshot)
           VALUES (?, ?)""",
        (module, context_snapshot)
    )
    session_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return session_id


def get_module_discovery_session(session_id: int) -> dict | None:
    """Get a module discovery session by id."""
    import json
    conn = _get_sync_conn()
    row = conn.execute(
        "SELECT * FROM module_discovery_sessions WHERE id = ?",
        (session_id,)
    ).fetchone()
    conn.close()

    if not row:
        return None

    result = dict(row)
    result['messages'] = json.loads(result['messages_json'])
    result['extracted_data'] = json.loads(result['extracted_data_json'])
    return result


def get_active_module_discovery(module: str) -> dict | None:
    """Get the current active discovery session for a module."""
    import json
    conn = _get_sync_conn()
    row = conn.execute(
        """SELECT * FROM module_discovery_sessions
           WHERE module = ? AND status = 'active'
           ORDER BY started_at DESC LIMIT 1""",
        (module,)
    ).fetchone()
    conn.close()

    if not row:
        return None

    result = dict(row)
    result['messages'] = json.loads(result['messages_json'])
    result['extracted_data'] = json.loads(result['extracted_data_json'])
    return result


def add_module_discovery_message(session_id: int, role: str, content: str) -> dict | None:
    """Add a message to a module discovery session."""
    import json
    from datetime import datetime

    conn = _get_sync_conn()
    row = conn.execute(
        "SELECT * FROM module_discovery_sessions WHERE id = ?",
        (session_id,)
    ).fetchone()

    if not row:
        conn.close()
        return None

    messages = json.loads(row['messages_json'])
    messages.append({
        'role': role,
        'content': content,
        'timestamp': datetime.now().isoformat()
    })

    conn.execute(
        """UPDATE module_discovery_sessions
           SET messages_json = ?
           WHERE id = ?""",
        (json.dumps(messages), session_id)
    )
    conn.commit()
    conn.close()

    return get_module_discovery_session(session_id)


def update_module_discovery_session(
    session_id: int,
    status: str | None = None,
    extracted_data_json: str | None = None,
    summary: str | None = None,
) -> dict | None:
    """Update a module discovery session."""
    conn = _get_sync_conn()

    updates = []
    values = []

    if status is not None:
        updates.append("status = ?")
        values.append(status)
        if status in ('completed', 'abandoned'):
            updates.append("ended_at = datetime('now')")

    if extracted_data_json is not None:
        updates.append("extracted_data_json = ?")
        values.append(extracted_data_json)

    if summary is not None:
        updates.append("summary = ?")
        values.append(summary)

    if not updates:
        conn.close()
        return get_module_discovery_session(session_id)

    values.append(session_id)
    conn.execute(
        f"UPDATE module_discovery_sessions SET {', '.join(updates)} WHERE id = ?",
        values
    )
    conn.commit()
    conn.close()

    return get_module_discovery_session(session_id)


# =============================================
# Nutrition helpers
# =============================================

def get_nutrition_profile() -> dict | None:
    """Get the nutrition profile."""
    conn = _get_sync_conn()
    row = conn.execute("SELECT * FROM nutrition_profile LIMIT 1").fetchone()
    conn.close()
    return dict(row) if row else None


def upsert_nutrition_profile(data: dict) -> dict:
    """Insert or update nutrition profile."""
    conn = _get_sync_conn()
    existing = conn.execute("SELECT id FROM nutrition_profile LIMIT 1").fetchone()

    allowed = {
        'weight_kg', 'goal_weight_kg', 'protein_target_g', 'calorie_target',
        'carb_target_g', 'fat_target_g', 'meals_per_day', 'eating_window',
        'restrictions_json', 'supplements_json', 'notes', 'discovery_session_id'
    }
    filtered = {k: v for k, v in data.items() if k in allowed}

    if existing:
        if filtered:
            set_clause = ", ".join(f"{k} = ?" for k in filtered.keys())
            conn.execute(
                f"UPDATE nutrition_profile SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
                list(filtered.values()) + [existing[0]]
            )
    else:
        if filtered:
            cols = ", ".join(filtered.keys())
            placeholders = ", ".join("?" for _ in filtered)
            conn.execute(
                f"INSERT INTO nutrition_profile ({cols}) VALUES ({placeholders})",
                list(filtered.values())
            )
        else:
            conn.execute("INSERT INTO nutrition_profile DEFAULT VALUES")

    conn.commit()
    conn.close()
    return get_nutrition_profile() or {}


def insert_food_entry(
    description: str,
    meal_type: str = 'snack',
    weight_g: float | None = None,
    protein_g: float | None = None,
    carbs_g: float | None = None,
    fat_g: float | None = None,
    calories: float | None = None,
    is_estimated: bool = True,
    audio_path: str | None = None,
    notes: str | None = None,
) -> int:
    """Insert a food entry. Returns entry id."""
    conn = _get_sync_conn()
    cursor = conn.execute("""
        INSERT INTO food_entries (description, meal_type, weight_g, protein_g, carbs_g, fat_g, calories, is_estimated, audio_path, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (description, meal_type, weight_g, protein_g, carbs_g, fat_g, calories, 1 if is_estimated else 0, audio_path, notes))
    entry_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return entry_id


def get_food_entries_today() -> list[dict]:
    """Get today's food entries."""
    conn = _get_sync_conn()
    rows = conn.execute("""
        SELECT * FROM food_entries
        WHERE date(timestamp) = date('now')
        ORDER BY timestamp
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_nutrition_daily_totals(date: str | None = None) -> dict:
    """Get daily nutrition totals."""
    conn = _get_sync_conn()
    date_filter = date or "date('now')"
    if date:
        rows = conn.execute("""
            SELECT SUM(protein_g) as protein, SUM(carbs_g) as carbs,
                   SUM(fat_g) as fat, SUM(calories) as calories
            FROM food_entries WHERE date(timestamp) = ?
        """, (date,)).fetchone()
    else:
        rows = conn.execute("""
            SELECT SUM(protein_g) as protein, SUM(carbs_g) as carbs,
                   SUM(fat_g) as fat, SUM(calories) as calories
            FROM food_entries WHERE date(timestamp) = date('now')
        """).fetchone()
    conn.close()

    return {
        'protein': rows['protein'] or 0,
        'carbs': rows['carbs'] or 0,
        'fat': rows['fat'] or 0,
        'calories': rows['calories'] or 0,
    }


# =============================================
# Exercise helpers
# =============================================

def _parse_json_list(raw: str | None) -> list:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def _normalize_set_entry(entry: dict) -> dict:
    reps = entry.get('reps')
    weight_kg = entry.get('weight_kg')
    rir = entry.get('rir')
    rpe = entry.get('rpe')

    try:
        reps = int(reps) if reps not in (None, '') else None
    except (TypeError, ValueError):
        reps = None

    try:
        weight_kg = float(weight_kg) if weight_kg not in (None, '') else 0.0
    except (TypeError, ValueError):
        weight_kg = 0.0

    try:
        rir = int(rir) if rir not in (None, '') else None
    except (TypeError, ValueError):
        rir = None

    try:
        rpe = int(rpe) if rpe not in (None, '') else None
    except (TypeError, ValueError):
        rpe = None

    return {
        'reps': reps,
        'weight_kg': weight_kg,
        'rir': rir,
        'rpe': rpe,
        'reached_failure': bool(entry.get('reached_failure')),
        'completed': bool(entry.get('completed', reps not in (None, 0))),
        'notes': (entry.get('notes') or '').strip() or None,
    }


def _estimate_1rm(weight_kg: float, reps: int) -> float | None:
    if weight_kg <= 0 or reps <= 0:
        return None
    if reps > 12:
        return None
    return round(weight_kg * (1 + reps / 30.0), 2)


def _summarize_sets(sets: list[dict]) -> dict:
    volume_load = 0.0
    hard_sets = 0
    best_weight = 0.0
    best_reps = 0
    best_estimated_1rm = 0.0

    for raw_set in sets:
        if not isinstance(raw_set, dict):
            continue
        set_entry = _normalize_set_entry(raw_set)
        reps = set_entry['reps'] or 0
        weight_kg = set_entry['weight_kg'] or 0.0
        volume_load += reps * weight_kg
        if reps > 0 and (
            set_entry['reached_failure']
            or set_entry['rir'] is None
            or (set_entry['rir'] is not None and set_entry['rir'] <= 3)
            or (set_entry['rpe'] is not None and set_entry['rpe'] >= 7)
        ):
            hard_sets += 1
        if weight_kg > best_weight or (weight_kg == best_weight and reps > best_reps):
            best_weight = weight_kg
            best_reps = reps
        estimated = _estimate_1rm(weight_kg, reps)
        if estimated and estimated > best_estimated_1rm:
            best_estimated_1rm = estimated

    return {
        'volume_load': round(volume_load, 2),
        'hard_sets': hard_sets,
        'best_set_weight_kg': round(best_weight, 2) if best_weight else 0.0,
        'best_set_reps': best_reps,
        'estimated_1rm': round(best_estimated_1rm, 2) if best_estimated_1rm else None,
    }


def _maybe_insert_personal_record(
    conn: sqlite3.Connection,
    *,
    session_id: int,
    exercise_name: str,
    best_weight_kg: float,
    best_reps: int,
    estimated_1rm: float | None,
    notes: str | None,
) -> bool:
    previous = conn.execute(
        """
        SELECT * FROM personal_records
        WHERE exercise_name = ?
        ORDER BY COALESCE(estimated_1rm, 0) DESC, weight_kg DESC, reps DESC, achieved_at DESC
        LIMIT 1
        """,
        (exercise_name,),
    ).fetchone()

    prev_estimated = float(previous['estimated_1rm'] or 0) if previous else 0.0
    prev_weight = float(previous['weight_kg'] or 0) if previous else 0.0
    prev_reps = int(previous['reps'] or 0) if previous else 0

    is_pr = False
    metric_type = 'estimated_1rm'

    if estimated_1rm and estimated_1rm > prev_estimated + 0.5:
        is_pr = True
        metric_type = 'estimated_1rm'
    elif best_weight_kg > prev_weight or (best_weight_kg == prev_weight and best_reps > prev_reps):
        is_pr = True
        metric_type = 'repetition' if best_weight_kg <= 0 else 'load_reps'

    if not is_pr:
        return False

    conn.execute(
        """
        INSERT INTO personal_records (exercise_name, weight_kg, reps, metric_type, estimated_1rm, session_id, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            exercise_name,
            best_weight_kg,
            best_reps,
            metric_type,
            estimated_1rm,
            session_id,
            notes,
        ),
    )
    return True


def list_exercise_equipment(location: str | None = None, active_only: bool = True) -> list[dict]:
    """List registered exercise equipment."""
    conn = _get_sync_conn()
    query = "SELECT * FROM exercise_equipment_items"
    clauses = []
    params: list = []
    if location:
        clauses.append("location = ?")
        params.append(location)
    if active_only:
        clauses.append("is_active = 1")
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY location, category, label"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def insert_exercise_equipment(
    *,
    location: str,
    category: str,
    label: str,
    max_load_kg: float | None = None,
    quantity: int | None = None,
    notes: str | None = None,
) -> int:
    """Insert a new equipment item."""
    conn = _get_sync_conn()
    cursor = conn.execute(
        """
        INSERT INTO exercise_equipment_items (location, category, label, max_load_kg, quantity, notes)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            location,
            category.strip(),
            label.strip(),
            max_load_kg,
            quantity or 1,
            notes,
        ),
    )
    item_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return item_id


def delete_exercise_equipment(item_id: int) -> None:
    """Soft-delete an equipment item."""
    conn = _get_sync_conn()
    conn.execute(
        "UPDATE exercise_equipment_items SET is_active = 0, updated_at = datetime('now') WHERE id = ?",
        (item_id,),
    )
    conn.commit()
    conn.close()


def get_body_measurement_snapshots(limit: int = 12) -> list[dict]:
    """Get measurement snapshots, newest first."""
    conn = _get_sync_conn()
    rows = conn.execute(
        """
        SELECT * FROM body_measurement_snapshots
        ORDER BY taken_on DESC, id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_latest_body_measurement_snapshot() -> dict | None:
    snapshots = get_body_measurement_snapshots(limit=1)
    return snapshots[0] if snapshots else None


def insert_body_measurement_snapshot(data: dict) -> dict:
    """Insert a body measurement snapshot and return it."""
    conn = _get_sync_conn()
    allowed = {
        'taken_on', 'weight_kg', 'waist_cm', 'hip_cm', 'chest_cm',
        'arm_relaxed_cm', 'arm_flexed_cm', 'thigh_cm', 'calf_cm', 'notes',
    }
    filtered = {k: v for k, v in data.items() if k in allowed}
    if 'taken_on' not in filtered or not filtered['taken_on']:
        filtered['taken_on'] = datetime.now().strftime("%Y-%m-%d")
    cols = ", ".join(filtered.keys())
    placeholders = ", ".join("?" for _ in filtered)
    cursor = conn.execute(
        f"INSERT INTO body_measurement_snapshots ({cols}) VALUES ({placeholders})",
        list(filtered.values()),
    )
    snapshot_id = cursor.lastrowid
    conn.commit()
    row = conn.execute("SELECT * FROM body_measurement_snapshots WHERE id = ?", (snapshot_id,)).fetchone()
    conn.close()
    return dict(row) if row else {}


def get_exercise_profile() -> dict | None:
    """Get the exercise profile."""
    conn = _get_sync_conn()
    row = conn.execute("SELECT * FROM exercise_profile LIMIT 1").fetchone()
    conn.close()
    if row:
        result = dict(row)
        result['equipment'] = _parse_json_list(result.get('equipment_json'))
        result['goals'] = _parse_json_list(result.get('goals_json'))
        result['limitations'] = _parse_json_list(result.get('limitations_json'))
        result['schedule_days'] = _parse_json_list(result.get('schedule_days_json'))
        result['barriers'] = _parse_json_list(result.get('barriers_json'))
        result['enjoyment'] = _parse_json_list(result.get('enjoyment_json'))
        equipment_items = list_exercise_equipment()
        result['equipment_items'] = equipment_items
        if equipment_items:
            equipment_labels = [item['label'] for item in equipment_items]
            equipment_categories = [item['category'] for item in equipment_items]
            result['equipment'] = list(dict.fromkeys(result['equipment'] + equipment_labels))
            result['equipment_categories'] = list(dict.fromkeys(equipment_categories))
        return result
    return None


def upsert_exercise_profile(data: dict) -> dict:
    """Insert or update exercise profile."""
    conn = _get_sync_conn()
    existing = conn.execute("SELECT id FROM exercise_profile LIMIT 1").fetchone()

    allowed = {
        'fitness_level', 'equipment_json', 'workout_days_per_week', 'time_per_workout_min',
        'goals_json', 'limitations_json', 'has_gym_access', 'gym_start_date',
        'mobility_focus', 'notes', 'discovery_session_id', 'minimum_session_min',
        'optimal_session_min', 'schedule_days_json', 'barriers_json', 'enjoyment_json',
        'preferred_location', 'preferred_split', 'primary_goal', 'height_cm',
        'training_history_notes'
    }
    filtered = {k: v for k, v in data.items() if k in allowed}

    if existing:
        if filtered:
            set_clause = ", ".join(f"{k} = ?" for k in filtered.keys())
            conn.execute(
                f"UPDATE exercise_profile SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
                list(filtered.values()) + [existing[0]]
            )
    else:
        if filtered:
            cols = ", ".join(filtered.keys())
            placeholders = ", ".join("?" for _ in filtered)
            conn.execute(
                f"INSERT INTO exercise_profile ({cols}) VALUES ({placeholders})",
                list(filtered.values())
            )
        else:
            conn.execute("INSERT INTO exercise_profile DEFAULT VALUES")

    conn.commit()
    conn.close()
    return get_exercise_profile() or {}


def get_workout_templates(level: str | None = None) -> list[dict]:
    """Get workout templates."""
    conn = _get_sync_conn()
    if level:
        rows = conn.execute(
            "SELECT * FROM workout_templates WHERE level = ? AND is_active = 1 ORDER BY id",
            (level,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM workout_templates WHERE is_active = 1 ORDER BY level, id"
        ).fetchall()
    conn.close()

    result = []
    for r in rows:
        d = dict(r)
        d['exercises'] = _parse_json_list(d.get('exercises_json'))
        result.append(d)
    return result


def insert_workout_template(
    name: str,
    level: str,
    exercises_json: str,
    workout_type: str | None = None,
    estimated_duration_min: int | None = None,
) -> int:
    """Insert a workout template."""
    conn = _get_sync_conn()
    cursor = conn.execute("""
        INSERT INTO workout_templates (name, level, workout_type, exercises_json, estimated_duration_min)
        VALUES (?, ?, ?, ?, ?)
    """, (name, level, workout_type, exercises_json, estimated_duration_min))
    template_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return template_id


def insert_workout_session(
    date: str,
    level: str,
    template_id: int | None = None,
    exercises_json: str | None = None,
    notes: str | None = None,
    energy_level: int | None = None,
    focus_code: str | None = None,
    planned_location: str | None = None,
    actual_location: str | None = None,
    duration_min: int | None = None,
    session_rpe: int | None = None,
    fallback_used: bool = False,
    plan_source: str | None = None,
    completed: int | None = None,
    exercise_logs: list[dict] | None = None,
) -> int:
    """Insert a workout session."""
    conn = _get_sync_conn()
    completed_value = (
        completed
        if completed is not None
        else (1 if exercise_logs or exercises_json else 0)
    )
    cursor = conn.execute("""
        INSERT INTO workout_sessions (
            date, level, template_id, focus_code, planned_location, actual_location,
            exercises_json, notes, energy_level, duration_min, session_rpe,
            fallback_used, plan_source, completed
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        date,
        level,
        template_id,
        focus_code,
        planned_location,
        actual_location,
        exercises_json,
        notes,
        energy_level,
        duration_min,
        session_rpe,
        1 if fallback_used else 0,
        plan_source or 'manual',
        completed_value,
    ))
    session_id = cursor.lastrowid

    if exercise_logs:
        rendered_exercises: list[dict] = []
        for raw_log in exercise_logs:
            exercise_name = (raw_log.get('exercise_name') or '').strip()
            if not exercise_name:
                continue
            raw_sets = raw_log.get('sets') or []
            if isinstance(raw_sets, str):
                try:
                    raw_sets = json.loads(raw_sets)
                except json.JSONDecodeError:
                    raw_sets = []
            normalized_sets = [
                _normalize_set_entry(item)
                for item in raw_sets
                if isinstance(item, dict)
            ]
            summary = _summarize_sets(normalized_sets)
            is_pr = _maybe_insert_personal_record(
                conn,
                session_id=session_id,
                exercise_name=exercise_name,
                best_weight_kg=summary['best_set_weight_kg'],
                best_reps=summary['best_set_reps'],
                estimated_1rm=summary['estimated_1rm'],
                notes=raw_log.get('notes'),
            )
            conn.execute(
                """
                INSERT INTO exercise_logs (
                    session_id, exercise_name, sets_json, movement_pattern, equipment_context,
                    location, volume_load, hard_sets, best_set_weight_kg, best_set_reps,
                    notes, is_personal_record
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    exercise_name,
                    json.dumps(normalized_sets, ensure_ascii=False),
                    raw_log.get('movement_pattern'),
                    raw_log.get('equipment_context'),
                    raw_log.get('location') or actual_location or planned_location,
                    summary['volume_load'],
                    summary['hard_sets'],
                    summary['best_set_weight_kg'],
                    summary['best_set_reps'],
                    raw_log.get('notes'),
                    1 if is_pr else 0,
                ),
            )
            rendered_exercises.append(
                {
                    'name': exercise_name,
                    'movement_pattern': raw_log.get('movement_pattern'),
                    'equipment_context': raw_log.get('equipment_context'),
                    'sets': normalized_sets,
                    'notes': raw_log.get('notes'),
                }
            )

        if rendered_exercises and not exercises_json:
            conn.execute(
                "UPDATE workout_sessions SET exercises_json = ? WHERE id = ?",
                (json.dumps(rendered_exercises, ensure_ascii=False), session_id),
            )

    conn.commit()
    conn.close()
    return session_id


def get_workout_sessions(limit: int = 30) -> list[dict]:
    """Get recent workout sessions."""
    conn = _get_sync_conn()
    rows = conn.execute("""
        SELECT ws.*, wt.name as template_name
        FROM workout_sessions ws
        LEFT JOIN workout_templates wt ON wt.id = ws.template_id
        ORDER BY ws.date DESC LIMIT ?
    """, (limit,)).fetchall()
    session_ids = [row['id'] for row in rows]
    log_map: dict[int, list[dict]] = {}
    if session_ids:
        placeholders = ", ".join("?" for _ in session_ids)
        log_rows = conn.execute(
            f"""
            SELECT * FROM exercise_logs
            WHERE session_id IN ({placeholders})
            ORDER BY id
            """,
            session_ids,
        ).fetchall()
        for row in log_rows:
            item = dict(row)
            item['sets'] = _parse_json_list(item.get('sets_json'))
            log_map.setdefault(item['session_id'], []).append(item)
    conn.close()

    result = []
    for r in rows:
        d = dict(r)
        d['exercises'] = _parse_json_list(d.get('exercises_json'))
        d['exercise_logs'] = log_map.get(d['id'], [])
        result.append(d)
    return result


def get_exercise_logs(limit: int = 50, exercise_name: str | None = None) -> list[dict]:
    """Get detailed exercise logs."""
    conn = _get_sync_conn()
    query = """
        SELECT el.*, ws.date, ws.level, ws.actual_location, ws.focus_code
        FROM exercise_logs el
        LEFT JOIN workout_sessions ws ON ws.id = el.session_id
    """
    params: list = []
    if exercise_name:
        query += " WHERE el.exercise_name = ?"
        params.append(exercise_name)
    query += " ORDER BY ws.date DESC, el.id DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()

    result = []
    for row in rows:
        item = dict(row)
        item['sets'] = _parse_json_list(item.get('sets_json'))
        result.append(item)
    return result


def get_personal_records(limit: int = 20) -> list[dict]:
    """Get recent personal records."""
    conn = _get_sync_conn()
    rows = conn.execute(
        """
        SELECT * FROM personal_records
        ORDER BY achieved_at DESC, id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_workout_adherence_summary(days: int = 28) -> dict:
    """Get recent workout adherence counts."""
    since = (datetime.now() - timedelta(days=max(days - 1, 0))).strftime("%Y-%m-%d")
    conn = _get_sync_conn()
    rows = conn.execute(
        """
        SELECT level, COUNT(*) as count
        FROM workout_sessions
        WHERE date >= ? AND completed = 1
        GROUP BY level
        """,
        (since,),
    ).fetchall()
    total = conn.execute(
        """
        SELECT COUNT(*) as count
        FROM workout_sessions
        WHERE date >= ? AND completed = 1
        """,
        (since,),
    ).fetchone()
    last_session = conn.execute(
        """
        SELECT date, level, actual_location, focus_code
        FROM workout_sessions
        WHERE completed = 1
        ORDER BY date DESC, id DESC
        LIMIT 1
        """
    ).fetchone()
    conn.close()

    counts = {'minimum': 0, 'optimal': 0}
    for row in rows:
        counts[row['level']] = row['count']

    return {
        'days': days,
        'since': since,
        'total_sessions': total['count'] if total else 0,
        'minimum_sessions': counts['minimum'],
        'optimal_sessions': counts['optimal'],
        'last_session': dict(last_session) if last_session else None,
    }


# =============================================
# Finance helpers
# =============================================

def get_finance_profile() -> dict | None:
    """Get the finance profile."""
    import json
    conn = _get_sync_conn()
    row = conn.execute("SELECT * FROM finance_profile LIMIT 1").fetchone()
    conn.close()
    if row:
        result = dict(row)
        result['fixed_expenses'] = json.loads(result.get('fixed_expenses_json') or '[]')
        result['debts'] = json.loads(result.get('debts_json') or '[]')
        return result
    return None


def upsert_finance_profile(data: dict) -> dict:
    """Insert or update finance profile."""
    conn = _get_sync_conn()
    existing = conn.execute("SELECT id FROM finance_profile LIMIT 1").fetchone()

    allowed = {
        'monthly_income', 'currency', 'fixed_expenses_json', 'debts_json',
        'savings_goal', 'emergency_fund_target', 'notes', 'discovery_session_id'
    }
    filtered = {k: v for k, v in data.items() if k in allowed}

    if existing:
        if filtered:
            set_clause = ", ".join(f"{k} = ?" for k in filtered.keys())
            conn.execute(
                f"UPDATE finance_profile SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
                list(filtered.values()) + [existing[0]]
            )
    else:
        if filtered:
            cols = ", ".join(filtered.keys())
            placeholders = ", ".join("?" for _ in filtered)
            conn.execute(
                f"INSERT INTO finance_profile ({cols}) VALUES ({placeholders})",
                list(filtered.values())
            )
        else:
            conn.execute("INSERT INTO finance_profile DEFAULT VALUES")

    conn.commit()
    conn.close()
    return get_finance_profile() or {}


def get_expense_categories() -> list[dict]:
    """Get all expense categories."""
    conn = _get_sync_conn()
    rows = conn.execute(
        "SELECT * FROM expense_categories ORDER BY sort_order"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def insert_expense(
    description: str,
    amount: float,
    category_code: str | None = None,
    is_recurring: bool = False,
    notes: str | None = None,
    payment_method: str | None = None,
    timestamp: str | None = None,
) -> int:
    """Insert an expense entry."""
    conn = _get_sync_conn()

    category_id = None
    if category_code:
        cat = conn.execute(
            "SELECT id FROM expense_categories WHERE code = ?", (category_code,)
        ).fetchone()
        if cat:
            category_id = cat['id']

    if timestamp:
        cursor = conn.execute("""
            INSERT INTO expenses (timestamp, description, amount, category_id, is_recurring, notes, payment_method)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (timestamp, description, amount, category_id, 1 if is_recurring else 0, notes, payment_method))
    else:
        cursor = conn.execute("""
            INSERT INTO expenses (description, amount, category_id, is_recurring, notes, payment_method)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (description, amount, category_id, 1 if is_recurring else 0, notes, payment_method))

    expense_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return expense_id


def get_expenses(limit: int = 50, month: str | None = None) -> list[dict]:
    """Get expenses, optionally filtered by month (YYYY-MM)."""
    conn = _get_sync_conn()
    if month:
        rows = conn.execute("""
            SELECT e.*, ec.code as category_code, ec.name_es as category_name, ec.icon as category_icon
            FROM expenses e
            LEFT JOIN expense_categories ec ON ec.id = e.category_id
            WHERE strftime('%Y-%m', e.timestamp) = ?
            ORDER BY e.timestamp DESC LIMIT ?
        """, (month, limit)).fetchall()
    else:
        rows = conn.execute("""
            SELECT e.*, ec.code as category_code, ec.name_es as category_name, ec.icon as category_icon
            FROM expenses e
            LEFT JOIN expense_categories ec ON ec.id = e.category_id
            ORDER BY e.timestamp DESC LIMIT ?
        """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_monthly_expense_summary(month: str | None = None) -> dict:
    """Get expense summary for a month."""
    conn = _get_sync_conn()
    month_filter = month or "strftime('%Y-%m', 'now')"

    if month:
        total_row = conn.execute("""
            SELECT SUM(amount) as total FROM expenses
            WHERE strftime('%Y-%m', timestamp) = ?
        """, (month,)).fetchone()

        by_category = conn.execute("""
            SELECT ec.code, ec.name_es, ec.icon, SUM(e.amount) as total
            FROM expenses e
            LEFT JOIN expense_categories ec ON ec.id = e.category_id
            WHERE strftime('%Y-%m', e.timestamp) = ?
            GROUP BY e.category_id
            ORDER BY total DESC
        """, (month,)).fetchall()
    else:
        total_row = conn.execute("""
            SELECT SUM(amount) as total FROM expenses
            WHERE strftime('%Y-%m', timestamp) = strftime('%Y-%m', 'now')
        """).fetchone()

        by_category = conn.execute("""
            SELECT ec.code, ec.name_es, ec.icon, SUM(e.amount) as total
            FROM expenses e
            LEFT JOIN expense_categories ec ON ec.id = e.category_id
            WHERE strftime('%Y-%m', e.timestamp) = strftime('%Y-%m', 'now')
            GROUP BY e.category_id
            ORDER BY total DESC
        """).fetchall()

    conn.close()

    return {
        'total': total_row['total'] or 0,
        'by_category': [dict(r) for r in by_category],
    }


# --- Audio migration helpers ---

def delete_diary_entry(entry_id: int) -> None:
    """Delete a diary entry by id (used to remove placeholder rows during migration)."""
    conn = _get_sync_conn()
    conn.execute("DELETE FROM diary_entries WHERE id = ?", (entry_id,))
    conn.commit()
    conn.close()


def update_diary_transcript_summary(entry_id: int, transcript: str, summary: str) -> None:
    """Update the raw_transcript and summary of an existing diary entry."""
    conn = _get_sync_conn()
    conn.execute(
        "UPDATE diary_entries SET raw_transcript = ?, summary = ? WHERE id = ?",
        (transcript, summary, entry_id),
    )
    conn.commit()
    conn.close()
