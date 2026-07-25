# Phase 5: Body (Nutricion + Ejercicio) & Finance — Quick Research & Design

> Iterative approach: Build working versions fast, iterate based on use.

---

## Core Principles (Aligned with Nash)

1. **Voice-first where it makes sense** — Nutrition logs via audio (natural)
2. **Minimal friction** — Quick entries, smart defaults
3. **Discovery conversations** — Gather context before tracking
4. **Nash opinions** — Analysis and recommendations based on data
5. **Integration** — These modules feed into overall life picture

---

## Module 1: Nutricion

### Purpose
Track macros simply. Focus on protein for muscle gain goal.

### Discovery Conversation Should Gather
- Current weight, goal weight
- Daily protein target (or calculate: ~1.6-2.2g per kg bodyweight)
- Daily calorie target (if known, or estimate)
- Eating patterns (meals per day, timing)
- Food preferences/restrictions
- Past diet attempts, what worked/failed
- Current supplements

### Data Model
```sql
-- Nutrition profile (from discovery)
nutrition_profile:
  weight_kg, goal_weight_kg, protein_target_g, calorie_target,
  meals_per_day, eating_window, restrictions_json, supplements_json

-- Daily food log
food_entries:
  id, timestamp, meal_type (breakfast/lunch/dinner/snack),
  description, weight_g, protein_g, carbs_g, fat_g, calories,
  estimated (bool), audio_path, notes

-- Daily summaries (auto-calculated)
nutrition_daily:
  date, total_protein, total_carbs, total_fat, total_calories,
  protein_target_met (bool), notes
```

### Input Flow
1. User records short audio: "almuerzo: 200g de pollo, arroz, ensalada"
2. Transcribe → Parse → Estimate macros if not provided
3. Show entry, allow quick edit
4. Update daily totals

### Protein Estimation Logic
- Common foods database (chicken breast ~31g/100g, rice ~2.7g/100g, etc.)
- LLM fallback for unusual foods
- User can override

---

## Module 2: Ejercicio

### Purpose
Track workouts, provide structure, ensure minimum movement.

### Discovery Conversation Should Gather
- Current fitness level (beginner/intermediate/advanced)
- Available equipment (home: dumbbells, bands, etc. + gym access soon)
- Time available per workout
- Days per week realistic
- Specific goals (muscle gain, mobility, strength)
- Injuries/limitations
- Past workout history, what stuck/failed
- Mobility issues (desk/bed lifestyle)

### Two-Level System
1. **Minimum** — "I don't want to workout but I should move"
   - 10-15 min
   - Basic movements, stretches, mobility
   - Can do at home with minimal equipment

2. **Optimal** — Full workout for muscle gain
   - 45-60 min
   - Progressive overload tracking
   - Compound movements focus
   - Split or full-body based on frequency

### Data Model
```sql
-- Exercise profile (from discovery)
exercise_profile:
  fitness_level, equipment_json, workout_days_per_week,
  time_per_workout_min, goals_json, limitations_json,
  has_gym_access, gym_access_date

-- Workout templates
workout_templates:
  id, name, level (minimum/optimal), type (push/pull/legs/full/mobility),
  exercises_json, estimated_duration_min, created_at

-- Workout sessions
workout_sessions:
  id, date, template_id, level, started_at, ended_at,
  exercises_json (actual performed), notes, energy_level, completed

-- Exercise log (individual exercises within session)
exercise_logs:
  id, session_id, exercise_name, sets_json [{reps, weight_kg, rpe}],
  notes, personal_record (bool)

-- Personal records
personal_records:
  exercise_name, weight_kg, reps, achieved_at
```

### Workout Generation
- Based on profile, generate weekly plan
- Adjust based on equipment (home vs gym)
- Track progressive overload (weight/reps increase)
- Mobility work built into minimum level

---

## Module 3: Dinero (Finance)

### Purpose
Track expenses, manage debt, allocate budget.

### Discovery Conversation Should Gather
- Monthly income (net)
- Fixed expenses (rent, subscriptions, loans)
- Variable expense categories
- Current debts (amounts, interest rates, minimum payments)
- Savings goals
- Financial stress points
- Spending patterns/weaknesses
- Current account balances

### Data Model
```sql
-- Finance profile (from discovery)
finance_profile:
  monthly_income, currency,
  fixed_expenses_json [{name, amount, due_day}],
  debts_json [{name, total, remaining, interest_rate, min_payment}],
  savings_goal, emergency_fund_target,
  expense_categories_json

-- Expense categories (predefined + custom)
expense_categories:
  id, code, name_es, icon, is_fixed, budget_amount, color

-- Expense entries
expenses:
  id, timestamp, description, amount, category_id,
  is_recurring, notes, payment_method

-- Monthly summaries
finance_monthly:
  year_month, income, total_expenses, by_category_json,
  savings, debt_payments, notes
```

### Predefined Expense Categories
- Vivienda (rent, utilities)
- Alimentacion (groceries, restaurants)
- Transporte (gas, uber, public)
- Salud (medical, pharmacy)
- Entretenimiento (streaming, games, outings)
- Educacion (courses, books)
- Deudas (loan payments)
- Ahorro (savings transfers)
- Personal (clothing, grooming)
- Otros (miscellaneous)

### Debt Strategy
- Show debt snowball or avalanche recommendation
- Track payments, remaining balance
- Project payoff dates

---

## Implementation Order

1. **Schema** — All three modules in one migration
2. **Discovery prompts** — Reuse goal_discovery pattern
3. **API endpoints** — CRUD for each module
4. **Frontend tabs** — Unlock Nutricion, Ejercicio, Dinero
5. **Discovery UIs** — Copy GoalDiscovery pattern
6. **Tracking UIs** — Simple entry forms/lists

---

## Quick Wins for V1

### Nutricion V1
- Discovery conversation
- Audio meal logging
- Daily protein total display
- Simple food entry list

### Ejercicio V1
- Discovery conversation
- View today's workout (minimum or optimal)
- Log completed exercises
- Simple progress view

### Dinero V1
- Discovery conversation
- Text expense entry
- Category totals
- Monthly overview

---

## Integration Points

- **Goals** — Financial goals, fitness goals connect to Metas
- **Profile** — Health data connects to Sobre Mi
- **Dashboard** — Summary across all modules (Phase 7)
- **Nash Context** — All data available to Nash for holistic advice

---

## Implementation Status (2026-04-05)

### Shipped in V1

- **Schema + helpers** for nutrition, exercise, finance, and module discovery sessions.
- **Module discovery engine** (`backend/agent/module_discovery.py`) with module-specific prompts and profile upserts.
- **Backend APIs** in `backend/main.py`:
  - `/{module}/discovery/*` for nutrition/exercise/finance
  - `/api/nutrition/*`, `/api/exercise/*`, `/api/finance/*`
- **Frontend tabs**:
  - `Cuerpo`: nutrition + exercise quick logging and history lists
  - `Dinero`: finance summary + expense logging and recent movement list
- **Reusable discovery modal** wired into `Cuerpo` and `Dinero`.

### Still Pending for Iteration

- Nutrition UI audio capture + automatic macro estimation from food text/audio.
- Default minimum/optimal workout templates and progression/personal-record views.
- Debt strategy guidance (avalanche/snowball), budget envelopes, recurring-payment visibility.
- Cross-module analytics in dashboard/meta layer.
