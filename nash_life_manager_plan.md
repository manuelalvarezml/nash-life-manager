---
name: Nash Life Manager
overview: Local, privacy-first AI life manager (Nash) — voice-first, LangGraph agent, modular tabs. Living plan; updated as implementation progresses.
reference_copy: "nash_life_manager_plan_reference.md (full research + long sections from Cursor export)"
todos:
  - id: phase1-infra
    content: "Phase 1: Ollama + models, Python layout, FastAPI, aiosqlite, ChromaDB client, ASR pipeline, LangGraph"
    status: completed
  - id: phase1-audio
    content: "Phase 1: Audio — file upload, save to data/audio, Parakeet ASR (ES+EN), brief summary, diary row"
    status: completed
  - id: phase1-agent
    content: "Phase 1: LangGraph ReAct, SqliteSaver (~/.nash/checkpoints.db), diary/memory/profile_fact tools, profile context"
    status: completed
  - id: phase1-ui
    content: "Phase 1: React+Vite — Home (mic+text), Historial, Lo que Nash sabe, Dev tab, SSE streaming"
    status: completed
  - id: phase1-profile-ui
    content: "Phase 1b: Perfil tab — diary highlights + optional synthesize; explain when facts/memories vs summaries update"
    status: completed
  - id: phase2-memory
    content: "Phase 2: SemanticDecomposer, semantic_units table, Chroma ingestion with nomic-embed-text, retrieval in agent context"
    status: completed
  - id: phase2-synth
    content: "Phase 2: ProfileSynthesizer auto-trigger (every 5 entries) + enhanced Dev tab with implementation status"
    status: completed
  - id: phase2-patterns
    content: "Phase 2: Hypothesis confidence, self-compassion hooks, question strategy adaptation"
    status: pending
  - id: phase2-questions-research
    content: "Phase 2b: QuestionEngine improvement research — direct/concrete questions vs vague/open"
    status: completed
  - id: phase3-goals-research
    content: "Phase 3: Goals deep research — hierarchy, self-concordance, implementation intentions, OKRs, time blocking"
    status: completed
  - id: phase3a-goals-foundation
    content: "Phase 3a: Goals Foundation — domains, ratings, basic goals, Metas tab"
    status: completed
  - id: phase3a-goal-discovery
    content: "Phase 3a+: Goal Discovery Conversation — conversational goal exploration with Nash, GROW+MI framework"
    status: completed
  - id: phase3b-goals-hierarchy
    content: "Phase 3b: Goals Hierarchy + OKRs — parent-child goals, key results"
    status: pending
  - id: phase3b-goal-graph-v1
    content: "Phase 3b (V1): Goal graph foundation — parent nesting + relation edges + discovery graph UI"
    status: completed
  - id: phase3c-goals-concordance
    content: "Phase 3c: Self-Concordance — coherence scoring, motivation tracking"
    status: pending
  - id: phase3d-goals-intentions
    content: "Phase 3d: Implementation Intentions — if-then planning"
    status: pending
  - id: phase3e-goals-timeblocks
    content: "Phase 3e: Time Blocking — calendar view, block creation"
    status: pending
  - id: phase4-self-profile-research
    content: "Phase 4: Self Profile Facts — deep research (McAdams, Schwartz, ACEs, biopsychosocial)"
    status: completed
  - id: phase4-self-profile-impl
    content: "Phase 4: Self Profile Facts — schema, API, Sobre Mí tab (core implementation)"
    status: completed
  - id: phase4-self-profile-guided
    content: "Phase 4: Self Profile — guided questions mode, conversation extraction"
    status: pending
  - id: historial-responses
    content: "Historial: Nash response saved + displayed, regenerate endpoint, clean recording stop"
    status: completed
  - id: historial-conversations
    content: "Historial: Conversation threads — user can reply to Nash (up to 5 exchanges, 11 messages total)"
    status: completed
  - id: phase5-body
    content: "Phase 5: Body (V1) — nutrition + workout tabs, discovery, and basic tracking flows"
    status: completed
  - id: phase5-body-iteration
    content: "Phase 5: Body iteration — nutrition audio parsing/estimation, default workout templates, PR tracking"
    status: pending
  - id: phase6-finance
    content: "Phase 6: Finance (V1) — finance tab, discovery, expense logging, monthly summary"
    status: completed
  - id: phase6-finance-iteration
    content: "Phase 6: Finance iteration — debt payoff strategy UX, statement PDF ingestion, loan-vs-card comparison, budget envelopes, recurring payments flow"
    status: pending
  - id: phase7-dashboard
    content: "Phase 7: Dashboard + Meta layer polish"
    status: pending
  - id: phase8-work
    content: "Phase 8: Work module — projects, todos, Flowmodoro, distractions"
    status: pending
  - id: phase9-macos
    content: "Phase 9: Tauri macOS"
    status: pending
  - id: nash-voice-output
    content: "Nash Voice Output — TTS for voice conversations, natural dialogue"
    status: pending
  - id: nash-expert-panel
    content: "Nash Expert Panel — Multi-agent debate system (5 experts analyze from different perspectives)"
    status: pending
  - id: nash-mcp-integration
    content: "MCP Integration — Model Context Protocol for specialized coaching tools"
    status: pending
isProject: true
---

# Nash Life Manager — Architecture & Build Plan

> **Source:** Migrated from Cursor plans into the repo (`nash_life_manager_plan.md`) for easy access. Long research sections from the original doc are summarized here; refer to git history or backups for the full narrative.

> **Change Log:** See `docs/CHANGELOG.md` for detailed record of changes including: what was before, why it didn't work, what we changed, why we think it will work, and what could go wrong. **Always update the changelog when making significant changes.**

## July 25, 2026 Direction Reset

- **Reasoning stack:** Nash is no longer "fully local" in the strict LLM sense. The default reasoning path is now **OpenAI API (`gpt-5.6`)** from the local machine, while SQLite, audio, ASR, checkpoints, and semantic vector storage stay local.
- **Privacy boundary:** Before remote LLM calls, outbound profile context, prompts, and user text are pseudonymized. By default the user's name is replaced with **`Antonio`**, while partner names, locations, emails, phone numbers, URLs, and long identifiers are generalized or masked. Local UI/storage restores the user-facing name so Nash does not start calling him Antonio in-app.
- **Finance priority:** The financial engine is now the highest-value module after daily entries. Nash's core agent context now includes income, debt snapshot, fixed expenses, recent expenses, and monthly category totals so advice can connect money patterns with emotional patterns.
- **Next finance step:** ingest monthly **credit card / loan PDFs**, group spending automatically, extract interest rates and debt structure, and compare repayment options (card payoff, loan refinance, asset sale such as the camera, etc.).

## Current implementation (Jul 2026)

| Area | Status |
|------|--------|
| **SQLite** | `~/.nash/nash.db` — diary (+nash_response), memories, profile_summaries, profile_facts, insights, **semantic_units**, **asked_questions**, **daily_question_answers**, **self_profile_facts**, **diary_conversations**, **life_domains**, **domain_ratings**, **goals** (with discovery fields + `parent_goal_id`), **goal_relations**, **goal_discovery_sessions** |
| **LangGraph checkpoints** | `~/.nash/checkpoints.db` (separate from app DB) |
| **Audio files** | `nash_life_manager/data/audio/` (`YYYYMMDD_HHMMSS_{type}.webm`), legacy copy from `~/.nash/audio/` on startup |
| **Transcription** | NVIDIA Parakeet from local path (`~/.nash/models/parakeet-tdt-0.6b-v3`) with auto backend selection (NeMo for TDT models; Transformers for compatible CTC models). NeMo long-audio chunking uses 120s chunks and rewinds to word `-15` from the previous chunk when word timestamps are available. |
| **After each voice upload** | Save audio → transcribe → **brief Spanish summary** → **insert diary row** → **semantic decomposition** → agent reply → **save Nash response to diary** |
| **Semantic Decomposition** | Extracts typed units (memory, pattern, feeling, etc.) from transcripts, stores in SQLite + **local Chroma embeddings** |
| **Frontend** | Tabs: Inicio, Historial, **Lo que Nash sabe**, **Sobre Mi**, **Metas**, **Cuerpo**, **Dinero**, Trabajo…, **Dev**. Vite proxies `/api` and `/media`. |
| **Home layout** | Top navigation bar (always visible), toggleable questions panel (40% right column), large mic button |
| **Historial** | Lists diary rows with summary, transcript snippet, optional audio player, **duration badge**, **expandable Nash response**, **regenerate responses button** |
| **Lo que Nash sabe** | Domain summaries (`profile_summaries`), facts (`log_profile_fact`), memories (`log_memory`), and **Regenerar resumenes** (synthesis from recent diaries) |
| **Agent Context** | **Self-profile biographical data** + **finance snapshot** (income, debts, fixed expenses, monthly spend, recent movements) + profile summaries + facts + **top-5 relevant semantic units** from Chroma retrieval |
| **Profile Synthesis** | **Auto-triggers every 5 diary entries** (background job) + manual "Regenerar resumenes" button |
| **QuestionEngine** | Daily generation endpoint works; parser normalized model outputs. **Research completed** for improved question types (see `docs/question_engine_improved_research.md`). |
| **Dev Tab** | Implementation status checklist, stats grid, color-coded facts, progress bar |
| **Sobre Mi** | Biographical profile editor — 11 sections (identity, family, career, values, life story, etc.), completeness tracking, auto-save |
| **UI Theme** | Vivid light palette: brick orange, teal, wine purple, prussian blue |
| **Metas Tab** | Wheel of Life domains (8), domain rating modal, goals list with filters, create/update/delete goals, progress tracking, self-concordance fields, **Goal Discovery** (conversation + floating graph + relation editing), hierarchy (`parent_goal_id`) + explicit relation edges |
| **Cuerpo + Dinero (V1)** | Backend endpoints for nutrition/exercise/finance + module discovery sessions; frontend tabs with quick forms (food log, workout session, expense log), profile summaries, and recent activity lists |

### When does "Lo que Nash sabe" fill in?

1. **Hechos** — When the agent calls `log_profile_fact` during chat (your explicit traits/patterns).
2. **Memorias** — When the agent calls `log_memory`.
3. **Resumenes por dominio** — Empty until you run **Regenerar resumenes** (calls the configured LLM provider on recent diary text) or until background synthesis refreshes them automatically.

## Language (updated)

- **UI & Nash replies:** Spanish.
- **Transcription:** Mixed ES/EN supported; **no translation** of stored transcripts for profiling nuance.
- **Code/comments:** English.

---

## Phase Roadmap

### Phase 2 — Memory & Self-Discovery (Current)

1. ~~**SemanticDecomposer** — structured multi-topic extraction; `semantic_units` table; embed units in Chroma.~~ **DONE**
2. ~~**Retrieval** — inject top-k semantic hits into agent context.~~ **DONE**
3. ~~**ProfileSynthesizer** — auto-trigger every 5 entries + enhanced Dev tab with implementation status.~~ **DONE**
4. ~~**QuestionEngine** — daily questions + `asked_questions` / `daily_question_answers`.~~ **DONE**
5. **QuestionEngine UX/perf** — improve "Generar ahora" latency messaging and optionally cache/retry strategy. **DEFERRED** (revisit after Phase 5-6, acceptable for now)
6. **Hypothesis confidence, self-compassion hooks, question strategy adaptation** — pending.

> **Decision (Apr 2026):** Proceeding to Phase 4 research while Phase 2 items 5-6 are deferred. The 20-40s question generation latency is acceptable for personal use. Will revisit UX polish after implementing more core features.

### QuestionEngine Improvement (Research Complete)

> **Research completed:** See `docs/question_engine_improved_research.md` for full analysis of why current questions feel vague and how to fix them.

**Problem:** Current questions feel too open-ended and therapeutic (e.g., "What patterns do you notice...?"), creating resistance.

**Solution:** Replace with more direct, concrete question types:

| Type | Example | Time to Answer |
|------|---------|----------------|
| **Scaling (1-10)** | "Del 1 al 10, ¿cómo te sientes con tu trabajo?" | 5 sec |
| **This-or-That** | "¿Prefieres más tiempo o más dinero?" | 5 sec |
| **Last Instance** | "¿Cuándo fue la última vez que te sentiste orgulloso?" | 30 sec |
| **Quick Fact** | "¿Cuántos años llevas en tu trabajo actual?" | 10 sec |
| **Single Most** | "¿Cuál es tu mayor preocupación financiera?" | 15 sec |
| **Tomorrow's Change** | "¿Qué cambiarías de tu rutina mañana?" | 20 sec |

**Key Insights:**
- Concrete > Abstract (ask about specific instances, not patterns)
- Quick > Deep (low friction builds consistency)
- Choice > Open-ended (binary choices are easier and still revealing)
- Follow-up matters (real insight comes from "why that number?")

**Daily Mix Recommendation:**
- 2 scaling questions (quick engagement)
- 1 this-or-that (low friction)
- 1 last instance (concrete experience)
- 1 quick fact OR single most (profile building)

**Implementation:** Pending — update `question_engine.py` prompt and question types.

### Phase 3 — Goals + Calendar + Time

> **Research completed:** See `docs/phase3_goals_research.md` for full synthesis of goal hierarchy theory, self-concordance, implementation intentions, personal OKRs, Wheel of Life, and intelligent calendar scheduling.

**Core Concepts from Research:**

| Concept | Description | Application |
|---------|-------------|-------------|
| **Goal Hierarchy** | Superordinate (abstract) → subordinate (concrete) goals | Every task traces to higher purpose |
| **Self-Concordance** | Goals aligned with intrinsic values/identity | Ask "why" for every goal; track motivation type |
| **Implementation Intentions** | "If [situation], then [action]" plans | Doubles/triples goal success rate |
| **Personal OKRs** | Objective + 2-3 measurable Key Results | Quarterly cycles with weekly reviews |
| **Wheel of Life** | 8-10 life domains rated 1-10 | Identify imbalances, set domain goals |
| **Time Blocking** | Schedule dedicated slots for goal work | AI-assisted priority protection |

**Schema Design (from research):**
- `life_domains` — Career, health, relationships, finance, etc.
- `domain_ratings` — Track satisfaction over time
- `goals` — Hierarchical with parent_goal_id, horizon, motivation_type
- `key_results` — OKR-style measurable outcomes
- `implementation_intentions` — If-then triggers per goal
- `time_blocks` — Calendar slots linked to goals

**Implementation Phases:**
1. ~~**3a: Foundation** — Domains + basic goals + satisfaction tracking~~ **DONE**
2. **3b: Hierarchy & OKRs** — Parent-child goals, key results, progress (**hierarchy + graph relations V1 done; key results pending**)
3. **3c: Self-Concordance** — Motivation type, "why it matters", coherence
4. **3d: Implementation Intentions** — If-then creation, reminders
5. **3e: Time Blocking** — Calendar view, block creation
6. **3f: Intelligent Features** — Conflict detection, auto-suggestions

**Phase 3a Completed (Apr 2026):**
- `life_domains` table with 8 Wheel of Life domains (seeded)
- `domain_ratings` table for tracking satisfaction over time
- `goals` table with horizon, status, progress, motivation_type, why_matters
- 9 API endpoints for domains and goals CRUD
- Metas tab with domain grid, rating modal, goals list, create/edit goals

---

#### Phase 3b: Goal Hierarchy + OKRs

**Objective:** Enable goals to have parent-child relationships and measurable key results.

**Database Changes:**

```sql
-- Add parent goal reference to goals table
ALTER TABLE goals ADD COLUMN parent_goal_id INTEGER REFERENCES goals(id);

-- Key Results table (OKR style)
CREATE TABLE IF NOT EXISTS key_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    goal_id INTEGER NOT NULL REFERENCES goals(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    metric_type TEXT NOT NULL CHECK (metric_type IN ('number', 'percentage', 'boolean', 'milestone')),
    target_value REAL,           -- For number/percentage types
    current_value REAL DEFAULT 0,
    unit TEXT,                   -- e.g., "kg", "books", "hours"
    milestones_json TEXT,        -- For milestone type: [{"label": "...", "done": false}, ...]
    due_date TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed', 'abandoned')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at TEXT
);

-- Index for quick lookups
CREATE INDEX idx_goals_parent ON goals(parent_goal_id);
CREATE INDEX idx_key_results_goal ON key_results(goal_id);
```

**Helper Functions (schema.py):**
- `get_goal_children(goal_id)` — Get all child goals
- `get_goal_hierarchy(goal_id)` — Get full tree from root to leaves
- `calculate_goal_progress(goal_id)` — Auto-calculate from key results
- `get_key_results(goal_id)` → list of KRs
- `insert_key_result(goal_id, title, metric_type, ...)` → KR id
- `update_key_result(kr_id, updates)` → updated KR
- `delete_key_result(kr_id)` → bool
- `update_kr_value(kr_id, new_value)` → recalculates goal progress

**API Endpoints (main.py):**
- `GET /api/goals/{id}/children` — Child goals
- `GET /api/goals/{id}/hierarchy` — Full goal tree
- `POST /api/goals/{goal_id}/key-results` — Create KR
- `GET /api/goals/{goal_id}/key-results` — List KRs for goal
- `PATCH /api/key-results/{id}` — Update KR
- `DELETE /api/key-results/{id}` — Delete KR
- `POST /api/key-results/{id}/update-value` — Quick value update

**Frontend (Metas.tsx):**
- Goal cards show child count badge
- Click goal → expand to show hierarchy view
- "Add sub-goal" button on each goal
- Key Results section when viewing a goal:
  - Progress bar per KR
  - Quick update slider/input for values
  - "Add Key Result" modal with metric type picker
- Auto-calculate parent goal progress from child goals + KRs

**Progress Calculation Logic:**
```python
def calculate_goal_progress(goal_id):
    # If goal has key results, progress = avg(KR completions)
    # If goal has children, progress = avg(child progresses)
    # If both, weighted average (60% KRs, 40% children)
    # If neither, use manual progress_pct
```

---

#### Phase 3c: Self-Concordance Enhancement

**Objective:** Help user track motivation alignment and detect goal conflicts.

**Database Changes:**

```sql
-- Add concordance fields to goals
ALTER TABLE goals ADD COLUMN concordance_score REAL;  -- 0-100, calculated
ALTER TABLE goals ADD COLUMN values_alignment TEXT;   -- JSON array of matched core values
ALTER TABLE goals ADD COLUMN last_reviewed TEXT;      -- When user last reflected on this goal

-- Concordance check history
CREATE TABLE IF NOT EXISTS concordance_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    goal_id INTEGER NOT NULL REFERENCES goals(id) ON DELETE CASCADE,
    motivation_then TEXT,        -- motivation_type at review time
    motivation_now TEXT,         -- updated motivation_type
    still_matters INTEGER,       -- 1-5 scale
    notes TEXT,
    reviewed_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

**Concordance Scoring Algorithm:**
```python
def calculate_concordance_score(goal):
    score = 0
    # Motivation type (0-40 points)
    motivation_scores = {
        'external': 10, 'introjected': 20,
        'identified': 30, 'intrinsic': 40
    }
    score += motivation_scores.get(goal.motivation_type, 0)

    # Has why_matters filled (0-30 points)
    if goal.why_matters and len(goal.why_matters) > 50:
        score += 30
    elif goal.why_matters:
        score += 15

    # Values alignment (0-30 points)
    # Compare goal tags/description with user's core_values from self_profile
    aligned_values = find_aligned_values(goal, user_core_values)
    score += min(30, len(aligned_values) * 10)

    return score
```

**API Endpoints:**
- `GET /api/goals/{id}/concordance` — Get concordance analysis
- `POST /api/goals/{id}/review` — Record concordance review
- `GET /api/goals/concordance-report` — All goals sorted by concordance
- `GET /api/goals/conflicts` — Detect conflicting goals

**Conflict Detection Logic:**
```python
def detect_conflicts(goals):
    conflicts = []
    # Time conflicts: overlapping target dates with heavy workload
    # Domain conflicts: competing priorities in same domain
    # Value conflicts: goals that pull in opposite directions
    # Resource conflicts: financial/time constraints
    return conflicts
```

**Frontend (Metas.tsx):**
- Concordance score badge on each goal (color-coded: red <40, yellow 40-70, green >70)
- "Review" button → modal asking:
  - "Does this goal still matter to you?" (1-5)
  - "Has your motivation changed?" (dropdown)
  - "Any thoughts?" (text)
- Concordance report view: goals sorted by alignment score
- Conflict alerts: banner when conflicts detected

---

#### Phase 3d: Implementation Intentions

**Objective:** Create "if-then" plans that research shows double/triple goal success rates.

**Database Changes:**

```sql
CREATE TABLE IF NOT EXISTS implementation_intentions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    goal_id INTEGER NOT NULL REFERENCES goals(id) ON DELETE CASCADE,
    if_situation TEXT NOT NULL,      -- "Si estoy en la oficina a las 3pm..."
    then_action TEXT NOT NULL,       -- "...entonces voy al gym por 30 min"
    cue_type TEXT CHECK (cue_type IN ('time', 'location', 'event', 'emotion', 'preceding_action')),
    cue_details_json TEXT,           -- {"time": "15:00", "days": ["mon", "wed", "fri"]}
    is_active INTEGER NOT NULL DEFAULT 1,
    times_triggered INTEGER DEFAULT 0,
    times_followed INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Track when intentions are followed
CREATE TABLE IF NOT EXISTS intention_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    intention_id INTEGER NOT NULL REFERENCES implementation_intentions(id),
    triggered_at TEXT NOT NULL DEFAULT (datetime('now')),
    was_followed INTEGER NOT NULL,   -- 0 or 1
    obstacle TEXT,                   -- Why not followed (if applicable)
    notes TEXT
);
```

**API Endpoints:**
- `GET /api/goals/{id}/intentions` — List intentions for goal
- `POST /api/goals/{id}/intentions` — Create intention
- `PATCH /api/intentions/{id}` — Update intention
- `DELETE /api/intentions/{id}` — Delete intention
- `POST /api/intentions/{id}/log` — Log trigger (followed/not)
- `GET /api/intentions/due` — Intentions that should trigger now/today

**Frontend (Metas.tsx):**
- "Add Implementation Intention" button on goal detail
- Intention builder wizard:
  1. Cue type selector (time, location, event, emotion, action)
  2. Specific cue input based on type
  3. Action input with auto-suggest from goal
  4. Preview: "Si [cue], entonces [action]"
- Intentions list on goal card
- Success rate badge (times_followed / times_triggered)
- "Did you follow through?" quick log buttons

**Cue Type Examples:**
| Type | Example Situation |
|------|-------------------|
| time | "Son las 7am de un día laboral" |
| location | "Llego a la oficina" |
| event | "Termino una reunión" |
| emotion | "Me siento estresado" |
| preceding_action | "Termino de almorzar" |

---

#### Phase 3e: Time Blocking

**Objective:** Schedule dedicated time slots for goal work, protected in calendar.

**Database Changes:**

```sql
CREATE TABLE IF NOT EXISTS time_blocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    goal_id INTEGER REFERENCES goals(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    description TEXT,
    start_time TEXT NOT NULL,        -- ISO datetime
    end_time TEXT NOT NULL,          -- ISO datetime
    recurrence_rule TEXT,            -- iCal RRULE format or simple: "weekly:mon,wed,fri"
    is_protected INTEGER DEFAULT 1,  -- Don't schedule over this
    actual_start TEXT,               -- When user actually started
    actual_end TEXT,                 -- When user actually ended
    completion_notes TEXT,
    status TEXT DEFAULT 'scheduled' CHECK (status IN ('scheduled', 'in_progress', 'completed', 'skipped', 'rescheduled')),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Quick index for date range queries
CREATE INDEX idx_time_blocks_range ON time_blocks(start_time, end_time);
```

**API Endpoints:**
- `GET /api/calendar/blocks?start=&end=` — Blocks in date range
- `POST /api/calendar/blocks` — Create block
- `PATCH /api/calendar/blocks/{id}` — Update block
- `DELETE /api/calendar/blocks/{id}` — Delete block
- `POST /api/calendar/blocks/{id}/start` — Mark block started
- `POST /api/calendar/blocks/{id}/complete` — Mark block completed
- `GET /api/calendar/suggestions?goal_id=` — AI suggests optimal times

**Frontend (new Calendar.tsx or Metas.tsx extension):**
- Week view calendar showing time blocks
- Drag-and-drop block creation
- Color-coded by goal/domain
- Block detail modal:
  - Link to goal
  - Actual time tracking
  - Completion notes
- "Schedule time for this goal" button on goal cards
- Recurring block setup (e.g., "Every Mon/Wed/Fri 7-8am")

**Calendar View Layout:**
```
┌────────────────────────────────────────────────────────┐
│  < Semana del 7 de abril >                    [+ Bloque]│
├────────┬────────┬────────┬────────┬────────┬────────┬──┤
│  Lun   │  Mar   │  Mié   │  Jue   │  Vie   │  Sáb   │Do│
├────────┼────────┼────────┼────────┼────────┼────────┼──┤
│ 7:00   │        │ 7:00   │        │ 7:00   │        │  │
│ ┌────┐ │        │ ┌────┐ │        │ ┌────┐ │        │  │
│ │Gym │ │        │ │Gym │ │        │ │Gym │ │        │  │
│ │🏃  │ │        │ │🏃  │ │        │ │🏃  │ │        │  │
│ └────┘ │        │ └────┘ │        │ └────┘ │        │  │
│        │ 9:00   │        │ 9:00   │        │        │  │
│        │ ┌────┐ │        │ ┌────┐ │        │        │  │
│        │ │Deep│ │        │ │Deep│ │        │        │  │
│        │ │Work│ │        │ │Work│ │        │        │  │
│        │ └────┘ │        │ └────┘ │        │        │  │
└────────┴────────┴────────┴────────┴────────┴────────┴──┘
```

---

#### Phase 3f: Intelligent Features

**Objective:** AI-assisted goal management, conflict detection, and auto-suggestions.

**Features:**

**1. Smart Goal Suggestions**
- Analyze profile gaps and domain ratings
- Suggest goals for neglected life areas
- "You haven't set any goals for 'Relationships' and rated it 4/10. Consider..."

**2. Conflict Detection**
```python
def detect_goal_conflicts():
    conflicts = []

    # Time conflicts
    # "Goal A needs 10hr/week, Goal B needs 8hr/week, you have 12hr available"

    # Financial conflicts
    # "Saving $X for Goal A while Goal B requires $Y purchase"

    # Value conflicts
    # "Goal A (career advancement) may conflict with Goal B (family time)"

    # Deadline conflicts
    # "3 goals with target dates in same week"

    return conflicts
```

**3. Weekly Review Generator**
- Auto-generate weekly review prompt based on:
  - Goals due this week
  - Key results to update
  - Intentions to check
  - Domain ratings due for refresh
- Presented in Home tab on Sundays/Mondays

**4. Progress Predictions**
```python
def predict_goal_completion(goal):
    # Based on:
    # - Current progress rate
    # - Historical completion patterns
    # - Time remaining
    # - Similar goals' outcomes
    return {
        'likely_date': '2026-06-15',
        'confidence': 0.72,
        'at_risk': False,
        'suggestion': 'Increase weekly time blocks by 2 hours'
    }
```

**5. Coherence Dashboard**
- Visual map of goal relationships
- Highlight goals supporting each other
- Warn about competing goals
- Show alignment with life theme (from self_profile)

**API Endpoints:**
- `GET /api/goals/smart-suggestions` — AI-generated goal suggestions
- `GET /api/goals/weekly-review` — Review items for the week
- `GET /api/goals/{id}/prediction` — Completion prediction
- `GET /api/goals/coherence-map` — Goal relationship data for visualization

**Frontend:**
- Weekly review card in Home tab
- Coherence visualization (network graph or sunburst chart)
- Conflict alerts banner
- "Nash suggests" section with goal recommendations

---

### Phase 4 — Self Profile Facts (Biographical Table)

> **Research completed:** See `docs/phase4_self_profile_research.md` for full synthesis of McAdams, Schwartz values, ACEs, biopsychosocial model, Wheel of Life, and therapeutic intake protocols.

**Purpose:** A rigid, structured table of factual biographical data about the user. This serves as foundational context for Nash's advisory capabilities across all modules.

**Key Insight from Research:** 85% of therapy outcome variance comes from common factors (client characteristics, therapeutic relationship) rather than specific techniques. Nash needs deep client knowledge — not just demographics, but values, patterns, formative experiences.

**Three Layers of Self-Knowledge:**

| Layer | Contents | How Nash Uses It |
|-------|----------|------------------|
| **Factual/Biographical** | Demographics, education, career, family, health | Base context for all interactions |
| **Narrative/Experiential** | Key memories, turning points, life chapters | Understanding "why" behind patterns |
| **Values/Identity** | Core values, beliefs, attachment style | Aligning advice with who user wants to be |

**Schema Sections (validated from research):**

| Section | Fields |
|---------|--------|
| **Core Identity** | birth_date, birth_place, gender, nationality, ethnicities |
| **Current Situation** | city, country, living_situation, years_at_location |
| **Family Origins** | mother/father (alive, age, occupation, relationship), parents_status, childhood context, siblings |
| **Education** | highest_education, field_of_study, schools_json |
| **Career** | current_occupation, industry, years_in_role, career_satisfaction, jobs_json |
| **Relationships** | status, partner, years, satisfaction, children, past relationships, patterns |
| **Health** | height, weight, chronic_conditions, medications, mental_health_history, attachment_style |
| **Values & Identity** | core_values (Schwartz), religious/spiritual, languages, MBTI, Big Five |
| **Life Story (McAdams)** | life_chapters_json, life_theme |
| **Preferences** | preferred_name, pronouns, timezone, communication_style |
| **Financial** | income_bracket, owns_home, financial_stress (optional) |

**Completeness Tracking:**
- Required fields (60% weight): basics for minimal context
- Recommended fields (40% weight): values, attachment, life theme
- Optional/sensitive: mental health, ACEs, financial details

**Implementation Steps:**
1. ~~`self_profile_facts` table with single row design~~ **DONE**
2. ~~API endpoints: GET /profile/self, PATCH /profile/self~~ **DONE**
3. ~~"Sobre Mí" tab with section cards + completeness meter~~ **DONE**
4. ~~Direct form entry for each section~~ **DONE**
5. Guided mode: Nash asks questions to fill gaps — pending
6. Conversation extraction: detect biographical info, suggest additions — pending
7. ~~Context integration: build_profile_context() for agent system prompt~~ **DONE**

**How This Feeds Other Phases:**
- **Goals (Phase 3)** — Align suggestions with core values
- **Body (Phase 5)** — Account for health conditions, medications
- **Finance (Phase 6)** — Contextualize with income bracket, financial stress
- **Dashboard (Phase 7)** — Show life stage, track against life theme
- **QuestionEngine** — Prioritize questions for unfilled profile gaps

**Distinction from Existing Profile System:**

| System | Purpose | How Populated |
|--------|---------|---------------|
| `profile_summaries` | AI-synthesized domain summaries (identity, patterns, sabotage, etc.) | ProfileSynthesizer runs on diary text |
| `profile_facts` | Observed traits/patterns logged by agent | Agent calls `log_profile_fact` during chat |
| `memories` | Specific episodes/stories | Agent calls `log_memory` during chat |
| `self_profile_facts` **(new)** | Rigid biographical facts | User enters directly or via guided questions |

The new `self_profile_facts` table provides **stable, factual foundation** that doesn't change often (birth date, family structure, education). The existing `profile_facts` captures **emergent patterns** that Nash observes over time. Both feed into agent context.

---

### Historial Improvements (Recent)

**Completed:**
- ~~Nash response saved to `diary_entries.nash_response` column~~ **DONE**
- ~~Expandable response section in Historial tab~~ **DONE**
- ~~Regenerate responses endpoint for existing entries~~ **DONE**
- ~~Clean recording stop (microphone stops immediately)~~ **DONE**

**Completed:**
- ~~**Conversation threads** — User can reply to Nash's response directly from Historial~~ **DONE**
  - Up to 5 back-and-forth exchanges (11 messages total: 1 initial + 5 user + 5 Nash)
  - **Voice or text replies** — Mic button for audio recording, transcribed automatically
  - Audio files stored with message, playable in conversation thread
  - New table: `diary_conversations` with `diary_entry_id`, `messages_json` (includes `audio_path`), `created_at`
  - Semantic decomposition runs on each exchange
  - Conversations feed into profile synthesis and semantic retrieval

---

### Phase 5 — Body (Nutrition + Workout)

**V1 shipped (Apr 2026):**
- Discovery conversations for nutrition and exercise (`/api/{module}/discovery/*`)
- Nutrition profile + daily totals + food entry logging (`/api/nutrition/*`)
- Exercise profile + templates + workout sessions (`/api/exercise/*`)
- `Cuerpo` tab with quick add flows and recent activity

**Next iteration:**
- Nutrition audio logging UX in tab (record from UI, not only API)
- Macro estimation when grams are missing (food dictionary + LLM fallback)
- Auto-seeded minimum/optimal templates and PR/progression views
- Better adherence analytics (weekly consistency + recovery flags)

### Phase 6 — Finance

**V1 shipped (Apr 2026):**
- Finance discovery conversation (`/api/finance/discovery/*`)
- Finance profile, categories, expenses, and monthly summary endpoints (`/api/finance/*`)
- `Dinero` tab with quick expense capture + category/month summary

**Next iteration:**
- Debt avalanche/snowball recommendation card with projections
- Budget envelope setup + alerts
- Recurring payment cadence views and upcoming due dates

### Phase 7 — Dashboard + Meta Layer

- Unified dashboard view
- Cross-module insights
- Pattern visualization
- Self-compassion prompts

### Phase 8 — Work Module

- Projects management
- Todo lists
- Flowmodoro timer
- Distraction tracking
- Work patterns

### Phase 9 — Tauri macOS

- Native macOS app wrapper
- System tray integration
- Global hotkeys
- Native notifications

---

## Future Features (Backlog)

### People Table

**Purpose:** Track people mentioned in conversations, questions, and reflections. Build a relationship map of the user's life.

**Schema (preliminary):**

```sql
CREATE TABLE people (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    relationship_type TEXT,  -- family, friend, colleague, romantic, etc.
    first_mentioned TEXT NOT NULL DEFAULT (datetime('now')),
    last_mentioned TEXT NOT NULL DEFAULT (datetime('now')),
    mention_count INTEGER NOT NULL DEFAULT 1,
    notes TEXT,
    -- Optional structured fields
    birth_year INTEGER,
    how_met TEXT,
    current_status TEXT  -- active, distant, deceased, etc.
);

CREATE TABLE people_mentions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER NOT NULL REFERENCES people(id),
    source_type TEXT NOT NULL,  -- diary, question_answer, memory
    source_id INTEGER NOT NULL,
    context_snippet TEXT,
    sentiment TEXT,  -- positive, negative, neutral, mixed
    mentioned_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

**Features:**
- Auto-detect names in transcripts and link to people records
- "People" tab showing relationship map
- Per-person view: all mentions, sentiment over time, relationship summary
- Agent can reference people context when relevant
- Questions can target specific relationships

**Implementation phase:** TBD (after Phase 7 or as part of advisory features)

---

## Architecture shorthand

- **Agent:** LangGraph `create_react_agent` + Ollama `drivedenpadev/deepseek-v3.2`.
- **Stack:** FastAPI, React+Vite+Tailwind, ChromaDB (client ready; full ingestion in Phase 2).

---

*End of living plan — extend sections below as modules ship.*
