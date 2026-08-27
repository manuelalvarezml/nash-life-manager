# Phase 3: Goals + Calendar + Time — Deep Research Synthesis

> **Date:** April 2026
> **Purpose:** Research foundation for Nash's goal management system — covering goal hierarchy theory, self-concordance, implementation intentions, time blocking, and intelligent calendar scheduling.

> **Implementation update (August 27, 2026):** Calendar Engine V1 is shipped. The original
> `time_blocks` concept evolved into separate input, suggestion, recurrence, occurrence, and history
> tables. This preserves provenance and creates an explicit consent boundary for diary/engine
> contributions. See `docs/calendar_memory_engine.md` for the implemented architecture and open
> hypotheses.

---

## Core Problem to Solve

Nash needs to help the user:
1. **Organize goals** across time horizons (daily, weekly, monthly, yearly, life)
2. **Ensure coherence** between actions and higher goals
3. **Self-organize calendar** to align time with priorities
4. **Track progress** without overwhelming the user
5. **Surface conflicts** between competing goals/values

---

## Part 1: Goal Hierarchy Theory

### What is a Goal Hierarchy?

Goals can be modeled as forming a hierarchy where **superordinate goals** (higher-level, abstract) are supported by **subordinate goals** (lower-level, concrete).

```
┌─────────────────────────────────────────┐
│ LIFE GOALS (superordinate)              │
│ "Live a meaningful, balanced life"       │
└────────────────┬────────────────────────┘
                 │
    ┌────────────┴────────────┐
    │                         │
┌───────────┐           ┌───────────┐
│ ANNUAL    │           │ ANNUAL    │
│ "Get fit" │           │ "Advance  │
│           │           │  career"  │
└─────┬─────┘           └─────┬─────┘
      │                       │
  ┌───┴───┐               ┌───┴───┐
  │       │               │       │
QUARTERLY QUARTERLY    QUARTERLY QUARTERLY
"Lose 5kg" "Run 5K"   "Promotion" "New skill"
      │
   WEEKLY
   "Gym 3x"
      │
    DAILY
  "Go today"
```

### Key Insights from Research

1. **Superordinate goals motivate long-term pursuit**: While subordinate goals drive immediate action, superordinate goals provide meaning and persistence when facing challenges.

2. **Both levels are necessary**: Locke and Latham (2004) note that goal-setting theory lacks "the issue of time perspective." Research extends this to show superordinate goals are crucial for broad, long-term challenges.

3. **Different neural circuits**: The brain processes short-term and long-term goals differently. Short-term goals activate immediate reward centers; long-term goals require different cognitive mechanisms.

4. **Construal Level Theory (CLT)**: People think about distant goals in abstract terms and near goals in concrete terms. This is natural and useful.

> **Sources:** [Frontiers in Psychology - Superordinate Goals](https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2018.01879/full), [PMC - Goal Hierarchies](https://pmc.ncbi.nlm.nih.gov/articles/PMC6176065/), [Journal of Management Studies](https://onlinelibrary.wiley.com/doi/10.1111/joms.13202)

---

## Part 2: Self-Concordance — Goals Aligned with Values

### What is Self-Concordance?

Self-concordance reflects how closely an individual's goals align with their intrinsic interests, values, and identity.

**Self-Determination Theory (SDT)** proposes a continuum of motivation:
- **External** → "I do this because others expect it"
- **Introjected** → "I do this to avoid guilt"
- **Identified** → "I do this because I value it"
- **Intrinsic** → "I do this because I enjoy it"

High self-concordance = goals driven by identified and intrinsic motivation.

### Why Self-Concordance Matters

Research by Sheldon and Elliot (1999) and subsequent studies show:

1. **Higher goal attainment**: Pursuing self-concordant goals leads to more effort and smoother achievement
2. **Increased well-being**: Self-concordant goal pursuit increases positive emotions and life satisfaction
3. **Sustained motivation**: Non-concordant goals lead to burnout and abandonment

### The Problem: System 1 vs System 2

> "One key reason for choosing misaligned goals is a disconnect between conscious thinking and deeper, less conscious motives. People often don't know what they truly want."

Goal-selection happens in verbal "System 2" which is somewhat disconnected from implicit inclinations in "System 1". This means people can choose and announce goals they don't actually care about.

### Measuring Self-Concordance

The **Relative Autonomy Index (RAI)** measures motivation on a continuum. For each goal, ask:
- "Why do you want this?" → External, introjected, identified, or intrinsic?

**Practical questions:**
```
"¿Por qué quieres lograr esta meta?"
- Porque otros esperan que lo haga (external)
- Porque me sentiría culpable si no lo hago (introjected)
- Porque creo que es importante (identified)
- Porque disfruto haciéndolo (intrinsic)
```

### Integration with Values

Research found:
- Self-transcendence and openness to change values → higher well-being
- This relationship is mediated by goal self-concordance
- Aligning healthy values with self-concordant goals leads to beneficial outcomes

> **Sources:** [Tech Science - Goal Self-Concordance](https://www.techscience.com/IJMHP/v23n2/42430/html), [Frontiers - Ego Identity](https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2024.1382345/full), [ScienceDirect - Free Will](https://www.sciencedirect.com/science/article/abs/pii/S2215091922000153)

---

## Part 3: Implementation Intentions — Closing the Intention-Behavior Gap

### The Problem

> "Although intentions to act qualify as predictors of behavior, accumulated evidence indicates that there is a substantial gap between even strong intentions and subsequent action."

Even with strong goals, people fail to act. Examples: exercise intentions, healthy eating, ethical purchases.

### What Are Implementation Intentions?

Implementation intentions are "if-then" plans that specify when, where, and how to act:

```
"If [situation], then [action]"

Examples:
- "If it's 7am on a weekday, then I will meditate for 10 minutes"
- "If I feel the urge to check my phone, then I will take 3 breaths first"
- "If I finish dinner, then I will immediately clean the dishes"
```

### Why They Work

1. **Automaticity**: Creates strong associative link between situation and action
2. **Reduces willpower needs**: Decision is pre-made
3. **Mental accessibility**: The cue becomes highly salient

### Research Evidence

- **Meta-analysis (Gollwitzer & Sheeran, 2006)**: 94 experiments, 8,000+ people
- **Effect**: Doubles or triples success rates
- **Domains**: Health, consumer choices, academics, personal goals

Example study: Participants who planned when/where to collect a coupon were **twice as likely** to redeem it.

### Combining with Self-Concordance

Studies found a **synergistic effect**: Implementation intentions work especially well when combined with self-concordant goals.

### Practical Application for Nash

For each goal, help user create:
```
META: [Goal statement + why it matters to them]
TRIGGERS: [List of if-then implementations]

Example:
META: "Quiero hacer ejercicio 3x/semana porque me da energía y claridad mental"
TRIGGERS:
- "Si es lunes/miércoles/viernes a las 7am → voy al gym"
- "Si estoy cansado y quiero saltármelo → hago solo 15 minutos"
- "Si llueve → hago ejercicio en casa"
```

> **Sources:** [Taylor & Francis - If-Then Planning](https://www.tandfonline.com/doi/full/10.1080/10463283.2020.1808936), [PMC - Implementation Intentions](https://pmc.ncbi.nlm.nih.gov/articles/PMC4500900/), [Wikipedia](https://en.wikipedia.org/wiki/Implementation_intention)

---

## Part 4: Personal OKRs — Adapting Business Frameworks

### Why OKRs Work for Personal Goals

OKRs (Objectives and Key Results) translate fuzzy goals into measurable outcomes:

**Objective**: Qualitative, inspiring, time-bound
**Key Results**: Quantitative, measurable (2-5 per objective)

### Personal OKR Examples

```
OBJECTIVE: Run a marathon in under 4 hours

KEY RESULTS:
- Join a marathon training group by [date]
- Train 5 days per week with 1 long run each week
- Increase weekly mileage by 5 miles per week
- Complete a half-marathon under 1:50 by [date]
```

```
OBJECTIVE: Be more present with family

KEY RESULTS:
- Home for dinner by 6pm at least 4 days/week
- Phone-free family time 2 hours every evening
- One full-day family activity per week
```

### Recommended Cadence

| Cycle | Focus |
|-------|-------|
| **Quarterly** | Set/review objectives |
| **Weekly** | Review key results, adjust |
| **Daily** | Tasks that move KRs forward |

> "A plan without accountability is just a wish list; OKRs add accountability because you review them regularly."

### Getting Started

1. Pick **one meaningful Objective** for the next quarter
2. Brainstorm **2-3 measurable Key Results**
3. Commit to **weekly review** (even 5 minutes)

> **Sources:** [What Matters - Personal OKRs](https://www.whatmatters.com/faqs/okrs-for-personal-life-goals-examples), [Eleganthack - Why Personal OKRs](https://eleganthack.com/why-use-personal-okrs/), [Todoist - OKRs Guide](https://www.todoist.com/productivity-methods/okrs-objectives-key-results)

---

## Part 5: Wheel of Life — Domain-Based Goal Setting

### What is the Wheel of Life?

A visual assessment tool dividing life into 8-10 domains, rating satisfaction in each (1-10), and identifying imbalances.

### Standard Domains

1. **Career & Work**: Job satisfaction, progression, work-life balance
2. **Finances**: Stability, debt management, financial goals
3. **Health**: Physical fitness, nutrition, mental health
4. **Relationships**: Romantic, friendships, social connections
5. **Family**: Parent/child relationships, extended family
6. **Personal Growth**: Learning, skills, self-improvement
7. **Recreation**: Hobbies, leisure, fun
8. **Environment**: Living space, physical surroundings
9. **Spirituality**: Meaning, purpose, beliefs (optional)
10. **Contribution**: Giving back, community, impact (optional)

### How It Works

1. Rate each domain 1-10
2. Visualize as wheel (how "round" is it?)
3. Identify 1-2 lowest areas
4. Set goals to improve those areas

### Key Insight

> "Balance isn't equal time everywhere; it's the right proportion guided by internal honesty."

### Integration with Nash

- Store domain satisfaction ratings over time
- Show trends (improving/declining areas)
- Suggest goals for neglected domains
- Alert when domains drop significantly

> **Sources:** [Quenza - Wheel of Life](https://quenza.com/blog/wheel-of-life-diagram/), [Scott Jeffrey - Assessment](https://scottjeffrey.com/wheel-of-life/), [Positive Psychology](https://positivepsychology.com/wheel-of-life-coaching/)

---

## Part 6: Intelligent Calendar & Time Blocking

### The Core Idea

Time blocking schedules every part of the day into dedicated slots for specific tasks/goals.

> "Time blocking helps you align your attention with your intentions."

### AI-Powered Calendar Tools (Market Research)

| Tool | Key Features |
|------|--------------|
| **Reclaim.ai** | Auto-protects tasks/habits, reshuffles on conflicts, saves ~7.6 hrs/week |
| **SkedPal** | Takes goals + preferences, builds optimal schedule |
| **TimeAlign** | Goals → plans → action, smartwatch integration |
| **Align** | Time blocking with explicit goal alignment |

### Key Mechanisms

1. **Priority-based scheduling**: Most important work protected first
2. **Auto-rescheduling**: When conflicts arise, tasks move automatically
3. **Capacity planning**: Maps tasks to actual availability
4. **Habit defense**: Recurring priorities get flexible holds

### Implementation for Nash

**Schema additions:**
```sql
CREATE TABLE time_blocks (
    id INTEGER PRIMARY KEY,
    goal_id INTEGER REFERENCES goals(id),
    day_of_week INTEGER,  -- 0-6
    start_time TEXT,      -- "09:00"
    end_time TEXT,        -- "10:00"
    is_flexible BOOLEAN,
    priority INTEGER      -- higher = harder to move
);
```

**Calendar Integration Points:**
- Morning: Show today's goal-aligned time blocks
- Evening: Review what got done vs planned
- Weekly: Suggest block adjustments based on patterns

> **Sources:** [Reclaim.ai](https://reclaim.ai/), [SkedPal](https://www.skedpal.com/), [Asana - Time Blocking](https://asana.com/resources/what-is-time-blocking), [TimeAlign](https://www.timealignapp.com/)

---

## Part 7: Coherence Between Actions and Goals

### The Coherence Problem

Users often:
- Set goals they don't work on
- Do tasks that don't serve any goal
- Have competing goals that conflict
- Lose sight of why they're doing things

### Nash's Role in Coherence

1. **Goal-Action Linking**
   - When user logs activity, ask: "¿A qué meta contribuye esto?"
   - Track % of time spent on goal-related vs unrelated activities

2. **Conflict Detection**
   - Surface when goals compete for same resources (time, money)
   - Example: "Your fitness goal and work goal both need 7am slots"

3. **Coherence Score**
   ```
   Coherence = (Time on goal activities / Total tracked time) ×
               (Goal self-concordance score)
   ```

4. **Weekly Coherence Review**
   - "Esta semana pasaste 60% del tiempo en actividades que no están conectadas a ninguna meta. ¿Quieres revisar tus metas?"

### Bridging Short-Term and Long-Term

For each daily/weekly task, Nash can show:
```
[Task]: Ir al gym
  ↓ contribuye a
[Weekly Goal]: Hacer ejercicio 3 veces
  ↓ contribuye a
[Quarterly Goal]: Bajar 5kg
  ↓ contribuye a
[Annual Goal]: Estar en buena forma física
  ↓ contribuye a
[Life Value]: Salud y energía
```

---

## Part 8: Proposed Schema & Architecture

### Database Tables

```sql
-- Life domains (based on Wheel of Life)
CREATE TABLE life_domains (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,           -- "career", "health", "relationships"
    display_name TEXT NOT NULL,   -- "Carrera", "Salud", "Relaciones"
    description TEXT,
    sort_order INTEGER
);

-- Domain satisfaction tracking
CREATE TABLE domain_ratings (
    id INTEGER PRIMARY KEY,
    domain_id INTEGER REFERENCES life_domains(id),
    rating INTEGER NOT NULL,      -- 1-10
    notes TEXT,
    rated_at TEXT DEFAULT (datetime('now'))
);

-- Goals with hierarchy
CREATE TABLE goals (
    id INTEGER PRIMARY KEY,
    parent_goal_id INTEGER REFERENCES goals(id),  -- NULL for top-level
    domain_id INTEGER REFERENCES life_domains(id),

    -- Core fields
    title TEXT NOT NULL,
    description TEXT,
    why_matters TEXT,             -- Self-concordance context

    -- Time horizon
    horizon TEXT NOT NULL,        -- 'life', 'annual', 'quarterly', 'monthly', 'weekly', 'daily'
    target_date TEXT,

    -- Status
    status TEXT DEFAULT 'active', -- 'active', 'completed', 'abandoned', 'paused'
    progress_pct INTEGER DEFAULT 0,

    -- Self-concordance
    motivation_type TEXT,         -- 'external', 'introjected', 'identified', 'intrinsic'
    concordance_score REAL,       -- 0-1, computed from motivation_type

    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Key Results (OKR style)
CREATE TABLE key_results (
    id INTEGER PRIMARY KEY,
    goal_id INTEGER REFERENCES goals(id),
    description TEXT NOT NULL,
    target_value REAL,
    current_value REAL DEFAULT 0,
    unit TEXT,                    -- "veces", "kg", "horas", etc.
    deadline TEXT
);

-- Implementation intentions
CREATE TABLE implementation_intentions (
    id INTEGER PRIMARY KEY,
    goal_id INTEGER REFERENCES goals(id),
    if_trigger TEXT NOT NULL,     -- "Es lunes a las 7am"
    then_action TEXT NOT NULL,    -- "Voy al gym"
    is_active BOOLEAN DEFAULT 1
);

-- Time blocks
CREATE TABLE time_blocks (
    id INTEGER PRIMARY KEY,
    goal_id INTEGER REFERENCES goals(id),
    day_of_week INTEGER,          -- 0=Mon, 6=Sun, NULL=any
    specific_date TEXT,           -- For one-time blocks
    start_time TEXT NOT NULL,     -- "09:00"
    end_time TEXT NOT NULL,       -- "10:00"
    priority INTEGER DEFAULT 5,   -- 1=movable, 10=immovable
    is_recurring BOOLEAN DEFAULT 0,
    status TEXT DEFAULT 'planned' -- 'planned', 'completed', 'missed', 'rescheduled'
);

-- Goal progress log
CREATE TABLE goal_progress_log (
    id INTEGER PRIMARY KEY,
    goal_id INTEGER REFERENCES goals(id),
    key_result_id INTEGER REFERENCES key_results(id),
    value_change REAL,
    notes TEXT,
    logged_at TEXT DEFAULT (datetime('now'))
);
```

### API Endpoints

```python
# Domains
GET  /api/goals/domains              # List all domains with latest ratings
POST /api/goals/domains/{id}/rate    # Rate a domain

# Goals
GET  /api/goals                      # List goals (filter by horizon, domain, status)
POST /api/goals                      # Create goal
GET  /api/goals/{id}                 # Get goal with children, KRs, intentions
PATCH /api/goals/{id}                # Update goal
POST /api/goals/{id}/progress        # Log progress

# Key Results
POST /api/goals/{id}/key-results     # Add key result
PATCH /api/key-results/{id}          # Update key result

# Implementation Intentions
POST /api/goals/{id}/intentions      # Add if-then intention
DELETE /api/intentions/{id}          # Remove intention

# Time Blocks
GET  /api/calendar/week              # Get week's time blocks
POST /api/calendar/blocks            # Create time block
PATCH /api/calendar/blocks/{id}      # Reschedule block

# Analysis
GET  /api/goals/coherence            # Get coherence metrics
GET  /api/goals/hierarchy            # Get full goal tree
GET  /api/goals/conflicts            # Detect competing goals
```

---

## Part 9: UI Concepts

### Goals Tab Structure

```
┌─────────────────────────────────────────────────┐
│ METAS                                    [+ Nueva] │
├─────────────────────────────────────────────────┤
│                                                 │
│ ◉ Rueda de la Vida                   [Actualizar] │
│   [Circular visualization with 8-10 domains]    │
│                                                 │
├─────────────────────────────────────────────────┤
│                                                 │
│ Horizonte: [Vida] [Año] [Trimestre] [Mes] [Sem] │
│                                                 │
│ ┌─────────────────────────────────────────────┐ │
│ │ 🎯 Estar en excelente forma física         │ │
│ │    Horizonte: Año | Dominio: Salud         │ │
│ │    Progress: ████████░░░░ 65%              │ │
│ │                                             │ │
│ │    KRs: 2/3 completados                    │ │
│ │    └ ✓ Bajar a 75kg (actual: 74kg)         │ │
│ │    └ ✓ Correr 5K en <25min                 │ │
│ │    └ ○ Gym 3x/semana sostenido             │ │
│ │                                             │ │
│ │    Sub-metas: 2 activas                    │ │
│ │    [Ver detalles]                          │ │
│ └─────────────────────────────────────────────┘ │
│                                                 │
└─────────────────────────────────────────────────┘
```

### Goal Detail View

```
┌─────────────────────────────────────────────────┐
│ ← Metas                                         │
├─────────────────────────────────────────────────┤
│                                                 │
│ 🎯 Estar en excelente forma física             │
│                                                 │
│ ┌─ Por qué importa ─────────────────────────┐  │
│ │ "Me da energía, claridad mental, y quiero  │  │
│ │  ser un ejemplo de salud para mi familia"  │  │
│ └───────────────────────────────────────────┘  │
│                                                 │
│ Motivación: Identificada + Intrínseca 🟢       │
│ Coherencia: Alta                                │
│                                                 │
│ ─── Resultados Clave ───                       │
│                                                 │
│ ✓ Bajar a 75kg                                 │
│   ████████████████ 100% (74kg de 75kg meta)    │
│                                                 │
│ ✓ Correr 5K en <25min                          │
│   ████████████████ 100% (24:30 actual)         │
│                                                 │
│ ○ Gym 3x/semana sostenido                      │
│   ████████░░░░░░░░ 50% (8/16 semanas)          │
│                                                 │
│ ─── Intenciones If-Then ───                    │
│                                                 │
│ • Si es L/M/V a las 7am → Voy al gym           │
│ • Si estoy cansado → Solo 15 min de cardio    │
│ • Si no puedo ir al gym → Hago ejercicio casa │
│                                                 │
│ ─── Bloques de Tiempo ───                      │
│                                                 │
│ Lun 7:00-8:00 | Mié 7:00-8:00 | Vie 7:00-8:00 │
│                                                 │
│ ─── Contribuye a ───                           │
│                                                 │
│ ↑ Vida saludable y activa (Meta de vida)       │
│                                                 │
│ ─── Metas derivadas ───                        │
│                                                 │
│ ↓ Bajar 2kg este mes (Meta mensual)            │
│ ↓ Ir al gym 3 veces esta semana (Meta semanal) │
│                                                 │
└─────────────────────────────────────────────────┘
```

---

## Part 10: Implementation Phases

### Phase 3a: Foundation
- Life domains table + Wheel of Life visualization
- Basic goals table (without hierarchy)
- Domain satisfaction tracking
- Goals API (CRUD)

### Phase 3b: Hierarchy & OKRs
- Parent-child goal relationships
- Key Results for each goal
- Progress tracking
- Horizon filters

### Phase 3c: Self-Concordance
- Motivation type selection on goal creation
- Concordance scoring
- "Why it matters" field
- Coherence alerts

### Phase 3d: Implementation Intentions
- If-then intention creation
- Link intentions to goals
- Morning intention reminders

### Phase 3e: Time Blocking
- Time blocks table
- Weekly calendar view
- Block creation/editing
- Integration with goals

### Phase 3f: Intelligent Features
- Conflict detection
- Auto-rescheduling suggestions
- Goal recommendation from diary themes
- Weekly coherence review

---

## Key Design Principles

1. **Start simple**: Basic goal tracking before complex features
2. **Self-concordance first**: Always ask "why" when creating goals
3. **Hierarchy awareness**: Every action should trace to higher purpose
4. **Flexible time**: Blocks should adapt, not constrain
5. **Non-judgmental tracking**: Missed blocks inform, not punish
6. **Diary integration**: Goals emerge from reflections

---

## References

### Goal Hierarchy & Theory
- [Frontiers - Superordinate Goals](https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2018.01879/full)
- [PMC - Goal Hierarchies](https://pmc.ncbi.nlm.nih.gov/articles/PMC6176065/)
- [Journal of Management Studies - Sub-Goal Interdependency](https://onlinelibrary.wiley.com/doi/10.1111/joms.13202)

### Self-Concordance
- [TechScience - Goal Self-Concordance Model](https://www.techscience.com/IJMHP/v23n2/42430/html)
- [Frontiers - Ego Identity Study](https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2024.1382345/full)
- [ScienceDirect - Using Free Will Wisely](https://www.sciencedirect.com/science/article/abs/pii/S2215091922000153)

### Implementation Intentions
- [Taylor & Francis - If-Then Planning](https://www.tandfonline.com/doi/full/10.1080/10463283.2020.1808936)
- [PMC - Implementation Intentions](https://pmc.ncbi.nlm.nih.gov/articles/PMC4500900/)
- [Wikipedia - Implementation Intention](https://en.wikipedia.org/wiki/Implementation_intention)

### Personal OKRs
- [What Matters - Personal OKRs](https://www.whatmatters.com/faqs/okrs-for-personal-life-goals-examples)
- [Eleganthack - Why Personal OKRs](https://eleganthack.com/why-use-personal-okrs/)
- [Todoist - OKRs Guide](https://www.todoist.com/productivity-methods/okrs-objectives-key-results)

### Wheel of Life
- [Quenza - Wheel of Life Diagram](https://quenza.com/blog/wheel-of-life-diagram/)
- [Scott Jeffrey - Assessment](https://scottjeffrey.com/wheel-of-life/)
- [Positive Psychology - Coaching](https://positivepsychology.com/wheel-of-life-coaching/)

### Intelligent Calendar
- [Reclaim.ai](https://reclaim.ai/)
- [SkedPal](https://www.skedpal.com/)
- [Asana - Time Blocking](https://asana.com/resources/what-is-time-blocking)
