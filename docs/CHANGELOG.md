# Nash Life Manager — Change Log & Decision Record

> This document tracks significant changes, the reasoning behind them, and potential risks.
> Always update this when making architectural or behavioral changes.

---

## 2026-08-27: Workout Engine v2 - Adherence-First Hypertrophy, Measurements, and Agent Integration

### Problem Statement
The original Body module was still too thin for the user's actual goal:

- it had workout logging, but not a real training engine built around **muscle gain with imperfect adherence**;
- Nash could not reliably connect workout recommendations to real-world constraints like home vs gym equipment, low-energy days, missed sessions, or emotional friction;
- there was no standardized measurement baseline for tracking physique change beyond scale weight;
- the exercise discovery flow was still tuned to a simpler V1 schema and could not capture barriers, enjoyment, minimum viable session length, or preferred training context.

This mattered because the project is not supposed to optimize for engagement or guilt. It needs to optimize for **actually getting Manuel to train consistently**, while preserving enough signal for Nash to coach him intelligently.

### What Changed
- Added a deterministic workout engine in `backend/exercise_engine.py`.
  - Generates a **primary session** plus a **home fallback rescue session**.
  - Chooses between **minimum** and **optimal** modes based on time, energy, and adherence.
  - Alternates A/B full-body structures for home and gym.
  - Tracks progression cues from previous logged performance.
  - Uses preference-aware exercise selection when the user has recorded what he enjoys.
- Expanded the exercise/body schema in `backend/db/schema.py`.
  - Added richer `exercise_profile` fields:
    - `minimum_session_min`, `optimal_session_min`, `schedule_days_json`, `barriers_json`, `enjoyment_json`, `preferred_location`, `preferred_split`, `primary_goal`, `height_cm`, `training_history_notes`
  - Added `exercise_equipment_items` for separate home/gym inventory.
  - Added `body_measurement_snapshots` for repeated anthropometric tracking.
  - Extended workout sessions and exercise logs with:
    - location context
    - duration
    - session RPE
    - fallback usage
    - volume/hard-set summaries
    - best-set fields
  - Personal records now capture metric type, estimated 1RM, session link, and notes.
- Expanded the API and `Cuerpo` tab so the workout engine is usable end to end.
  - Dashboard endpoint for current training state
  - Plan-generation endpoint
  - Equipment CRUD
  - Measurement logging
  - PR history
  - Set-by-set workout logger with reps, load, RIR, RPE, failure flag, and completion flag
- Integrated workout state into Nash's main reasoning context in `backend/agent/profile.py`.
  - Nash now sees:
    - body goal and fitness level
    - weekly structure and minimum floor
    - barriers and things the user enjoys
    - adherence in the last 7/28 days
    - latest measurements
    - recent PRs and recent sessions
    - today's suggested plan and rescue option
- Updated `backend/agent/prompts.py` so Nash explicitly treats workout adherence like the product intends:
  - protect the minimum viable session first;
  - use the home fallback when gym friction appears;
  - do **not** prescribe all-out failure on every exercise.
- Upgraded exercise discovery in `backend/agent/module_discovery.py`.
  - Discovery now extracts the richer exercise profile fields and frames the minimum plan as a success case rather than a consolation prize.
- Added UI guardrails in `frontend/src/components/tabs/Cuerpo.tsx`.
  - Invalid numeric inputs are rejected before save.
  - Measurements now show the actual site-by-site protocol in the interface.

### Why This Should Help
- The workout engine now matches the user's actual psychology:
  - **consistency first**
  - **minimum viable action as a win**
  - **fallback over self-blame**
- It also matches current hypertrophy evidence better:
  - training to failure is **not required** for growth in general;
  - frequency can be chosen largely by preference when weekly volume is handled;
  - meaningful progress can come from modest, time-efficient resistance training;
  - home-based resistance work is viable when equipment and progression are handled intelligently.
- Measurements are now standardized enough to detect change without turning the app into a laboratory. That gives Nash better signal for physique progress, especially when scale weight alone is ambiguous.

### Decisions Recorded
- **We did not center the engine on failure.**
  - Compounds default to roughly `1-3 RIR`.
  - Safer isolation work can move closer to failure when technique is still clean.
  - Reason: current meta-analytic evidence does not support "failure everywhere" as necessary for hypertrophy, and it would likely hurt adherence.
- **We chose an adherence-first deterministic planner instead of an LLM-only workout generator.**
  - Reason: the minimum floor, fallback logic, progression summaries, and equipment constraints need predictable behavior every day.
- **We chose repeated circumference + weight tracking rather than scale-only tracking.**
  - Reason: muscle gain and recomposition can be missed if we only watch bodyweight.

### Risks / Watchouts
- The planner is intentionally conservative. It is better at keeping the user in the game than at maximizing short-term training novelty.
- Enjoyment/barrier adaptation is keyword-driven for now; it is useful, but not yet a full behavioral model.
- Calendar auto-scheduling and nutrition-driven workout adjustments are still partial:
  - the workout engine already bridges to protein progress;
  - true calendar automation remains a later phase.
- Measurement quality still depends on consistent self-measurement technique.

### Validation
- Backend compile:
  - `./.venv/bin/python -m py_compile backend/db/schema.py backend/exercise_engine.py backend/main.py backend/agent/profile.py backend/agent/module_discovery.py backend/agent/prompts.py backend/llm.py` ✅
- Frontend build:
  - `npm run build` ✅
- Workout-context smoke test:
  - `build_profile_context(...)` produced a valid context after `init_db_sync()` ✅
- Workout-plan smoke test:
  - `generate_workout_plan()` returned a primary session and home fallback session ✅
- OpenAI provider initialization check:
  - `get_chat_model(...)` initialized successfully using the local `NASH_OPENAI_API_KEY` ✅

### Files Modified
- `backend/db/schema.py`
- `backend/exercise_engine.py`
- `backend/main.py`
- `backend/agent/profile.py`
- `backend/agent/module_discovery.py`
- `backend/agent/prompts.py`
- `frontend/src/api.ts`
- `frontend/src/components/tabs/Cuerpo.tsx`
- `nash_life_manager_plan.md`
- `docs/phase5_body_finance_research.md`
- `CONTEXT_HANDOFF.md`
- `docs/CHANGELOG.md`

## 2026-07-25: OpenAI Reasoning Migration + Privacy Boundary + Finance Context Reset

### Problem Statement
The app's intelligence layer was still centered on Ollama assumptions from April 2026:

- every reasoning path (`graph`, summaries, question generation, discovery, semantic decomposition) expected Ollama;
- prompts still claimed that Nash was fully local, which became false as soon as we wanted better reasoning from the OpenAI API;
- the core agent did **not** see finance profile data or recent spending, so it could not behave like the debt-aware financial advisor the user now needs;
- semantic retrieval still depended on Ollama embeddings, which meant the OpenAI migration would leave a hidden local-LLM dependency in the memory path.

### What Changed
- Added a shared LLM gateway in `backend/llm.py`.
  - Default provider is now **OpenAI** via `NASH_LLM_PROVIDER=openai`.
  - Default model is **`gpt-5.6`**.
  - Ollama remains available as an explicit fallback.
- Wired all main reasoning call sites to the shared gateway:
  - `backend/agent/graph.py`
  - `backend/audio/brief_summary.py`
  - `backend/agent/profile_synthesize.py`
  - `backend/agent/question_engine.py`
  - `backend/agent/semantic_decomposer.py`
  - `backend/agent/module_discovery.py`
  - `backend/agent/goal_discovery.py`
- Added an outbound privacy boundary for remote LLM requests:
  - user name is pseudonymized to **`Antonio`** by default (`NASH_REMOTE_ALIAS_NAME`);
  - partner names, locations, emails, phone numbers, URLs, and long identifiers are generalized or masked before outbound requests;
  - local UI/storage restores the user-facing name so the app does not start talking to Manuel as "Antonio."
- Updated prompts so they no longer falsely claim Nash is 100% local and so they explicitly handle finance conversations with concrete, non-judgmental advisory language.
- Expanded agent context in `backend/agent/profile.py`:
  - added finance snapshot injection (income, debts, fixed expenses, recent expenses, monthly category totals);
  - this lets Nash connect diary/emotional patterns with real money data.
- Removed the last default Ollama dependency from semantic retrieval:
  - Chroma now defaults to **local ONNX MiniLM embeddings**;
  - existing semantic units are rebuilt from SQLite into a provider-specific local collection on first query.
- Added root `.gitignore` and OpenAI dependencies to `requirements.txt`.

### Why This Should Help
- The reasoning quality jumps immediately by moving the high-value thinking work to a stronger API model.
- The privacy boundary reduces direct identity leakage without adding a heavy local preprocessing model or token-hungry prompt ceremony.
- Finance advice becomes more grounded because Nash can finally see debt/spending state in the same context window as the psychological profile.
- Memory retrieval stays local and keeps working even when Ollama is completely off.

### Risks / Watchouts
- OpenAI Responses-style content comes back as structured blocks, not always plain strings. We added normalization helpers, but future endpoints should reuse them instead of assuming `.content` is a bare string.
- The first local embedding query downloads Chroma's ONNX model once (~79 MB) into `~/.cache/chroma/`.
- Pseudonymization is helpful but not perfect. Free-text diary content can still contain identifying facts that regex/generalization will not always catch.
- Finance advice is now better informed, but the actual **statement PDF ingestion**, **loan comparison**, and **repayment simulator** are still pending.

### Validation
- Backend compile:
  - `./.venv/bin/python -m py_compile backend/config.py backend/db/schema.py backend/db/chroma.py backend/llm.py backend/agent/profile.py backend/agent/prompts.py backend/agent/graph.py backend/audio/brief_summary.py backend/agent/profile_synthesize.py backend/agent/question_engine.py backend/agent/semantic_decomposer.py backend/agent/module_discovery.py backend/agent/goal_discovery.py backend/main.py` ✅
- OpenAI provider smoke test:
  - `get_chat_model(...).invoke(...)` returned `OK` using the local `NASH_OPENAI_API_KEY` ✅
- Brief summary smoke test:
  - outbound aliasing happened remotely and local-name restoration returned "Manuel" in the final stored summary ✅
- LangGraph agent smoke test:
  - `graph.invoke(...)` initialized with `provider=openai` and returned a valid assistant response ✅
- Semantic retrieval smoke test:
  - local ONNX embedding model downloaded successfully and semantic index rebuilt from SQLite (`units=57`) ✅

### Files Modified
- `backend/config.py`
- `backend/llm.py`
- `backend/db/schema.py`
- `backend/db/chroma.py`
- `backend/agent/profile.py`
- `backend/agent/prompts.py`
- `backend/agent/graph.py`
- `backend/audio/brief_summary.py`
- `backend/agent/profile_synthesize.py`
- `backend/agent/question_engine.py`
- `backend/agent/semantic_decomposer.py`
- `backend/agent/module_discovery.py`
- `backend/agent/goal_discovery.py`
- `backend/main.py`
- `requirements.txt`
- `.gitignore`
- `ENVIRONMENT.md`
- `CONTEXT_HANDOFF.md`
- `nash_life_manager_plan.md`
- `docs/CHANGELOG.md`

## 2026-04-21: ASR Chunking — 2-Minute Segments + Word-Based Rewind

### Problem Statement
Long voice entries were being split with a fixed seconds-based overlap. This can cut Spanish speech at unnatural boundaries and may contribute to occasional language drift or recognition errors when a segment contains one English word or starts without enough Spanish context.

### What Changed
- Changed default `ASR_CHUNK_LENGTH_S` from 40 seconds to **120 seconds** in `backend/config.py`.
- Added `ASR_REWIND_WORDS` with default **15**.
- Reworked NeMo/Parakeet long-audio chunking in `backend/audio/transcriber.py`:
  - asks NeMo for word timestamps per chunk when available;
  - starts the next chunk at the timestamp of word `-15` from the previous chunk;
  - falls back to estimating that word position from transcript word count if timestamps are unavailable;
  - keeps boundary deduplication to remove repeated words from the rewind window.
- Updated environment/context/plan docs with the new ASR chunking behavior.

### Why This Should Help
The model gets a longer 2-minute acoustic/language context and the seam moves to a natural word boundary rather than a fixed 8-second overlap. That should reduce bad boundary effects and lower the chance that a tiny English phrase pushes a chunk toward English-like decoding.

### Risks / Watchouts
- 120-second chunks use more memory than 40-second chunks. If memory pressure returns, override with `ASR_CHUNK_LENGTH_S=60` when launching the backend.
- Word timestamps depend on NeMo support for the current model. If unavailable, the fallback estimates the word position from word count.

### Validation
- Backend compile: `./.venv/bin/python -m py_compile backend/config.py backend/audio/transcriber.py backend/main.py` ✅

### Files Modified
- `backend/config.py`
- `backend/audio/transcriber.py`
- `ENVIRONMENT.md`
- `CONTEXT_HANDOFF.md`
- `nash_life_manager_plan.md`
- `docs/CHANGELOG.md`

---

## 2026-04-08: Typed Life Graph v1 for `Metas`

### Problem Statement
The original `Metas` engine treated every node as a generic goal. We needed to evolve it into a typed life graph so Manuel can model identities, outcome goals, systems, and concrete actions in one graph, while preserving existing data and current editing flows.

### What Changed
- **Database / schema (`backend/db/schema.py`):**
  - Extended `goals` with `node_type`, `cadence_text`, `time_cost_min`, `energy_cost`, and `attention_cost`.
  - Migrated existing databases so prior rows become `node_type='goal'`.
  - Rebuilt the `goals` table shape to allow horizon to be optional/null when the node type requires it.
  - Expanded `goal_relations` to accept the new canonical edge types: `drives`, `requires`, `reinforces`, `conflicts_with`, `costs`, while preserving legacy relation types.
  - Added hierarchy validation by node type:
    - `identity` -> `goal | system`
    - `goal` -> `goal | system | action`
    - `system` -> `action`
    - `action` -> no children
  - Added type-aware normalization:
    - horizon only for `goal` and optional for `system`
    - cadence only for `system`
    - cost fields only for `action`
- **Discovery backend (`backend/agent/goal_discovery.py`):**
  - Reworked discovery into typed node extraction with strict `[NODO_IDENTIFICADO] ... [/NODO_IDENTIFICADO]`.
  - Added strict relation extraction with `[RELACION_IDENTIFICADA] ... [/RELACION_IDENTIFICADA]`.
  - Discovery now stages both nodes and relations in the same turn.
  - Kept backward compatibility with legacy `[META_IDENTIFICADA]` blocks, mapping them to `node_type='goal'`.
  - Added `extracted_relations_json` storage to discovery sessions.
- **API layer (`backend/main.py`, `frontend/src/api.ts`):**
  - Extended goals payloads/responses with typed-node fields.
  - `GET /api/goals` now supports `node_type` filtering.
  - Goal discovery chat responses now include `extracted_relations`.
  - Frontend typing now models node types, nullable horizon, cadence, action costs, and typed extracted relations.
- **`Metas` UI (`frontend/src/components/tabs/Metas.tsx`):**
  - Added type filter (`identity`, `goal`, `system`, `action`) while keeping “all node types” as the default view.
  - Added node-type signaling in the graph and cards without removing child-count coloring.
  - Updated graph side card and creation modal to be type-aware:
    - `Identity`: no horizon
    - `Goal`: destination-state node with horizon
    - `System`: cadence + optional horizon
    - `Action`: action-cost fields and no horizon
  - Parent selector now filters to only valid parent types.
- **`GoalDiscovery` UI (`frontend/src/components/GoalDiscovery.tsx`):**
  - Pending extracted nodes now support typed editing before save.
  - Pending extracted relations are now staged in the graph and selectable/editable before persistence.
  - Saving discovered nodes now attempts to persist any newly-resolvable pending relations automatically.
  - Saved-node editor inside discovery is now type-aware too.

### Validation
- Backend compile: `./.venv/bin/python -m py_compile backend/db/schema.py backend/main.py backend/agent/goal_discovery.py` ✅
- Frontend build: `npm run build` ✅

### Files Modified
- `backend/db/schema.py`
- `backend/main.py`
- `backend/agent/goal_discovery.py`
- `frontend/src/api.ts`
- `frontend/src/components/tabs/Metas.tsx`
- `frontend/src/components/GoalDiscovery.tsx`

---

## 2026-04-07: Goals `Fecha de inicio` Field — Existing + Future Nodes

### Problem Statement
Goal nodes needed a dedicated `Fecha de inicio` field that is available for existing goals and preserved in the data model for every newly created goal.

### What Changed
- **Database / schema (`backend/db/schema.py`):**
  - Added `start_date` column to `goals` table schema.
  - Added migration rule to create `start_date` in existing databases.
  - Backfilled existing goals with `date(created_at)` when `start_date` was null.
  - Extended `insert_goal(...)` and `update_goal(...)` allowed fields to handle `start_date`.
- **API layer (`backend/main.py`):**
  - `POST /api/goals` now accepts `start_date`.
  - `PATCH /api/goals/{id}` docs updated to include `start_date`.
- **Goal discovery extraction (`backend/agent/goal_discovery.py`):**
  - Prompt/output format now supports `fecha_inicio`.
  - Parser maps `fecha_inicio` -> `start_date` and validates date format.
  - Discovery save flow passes `start_date` when persisting extracted goals.
- **Frontend typing and UI:**
  - Added `start_date` to goal and extracted-goal types in `frontend/src/api.ts`.
  - Added `Fecha de inicio` in `Metas`:
    - new-goal modal
    - graph side card (read + edit)
    - list card metadata line
  - Added `Fecha de inicio` in `GoalDiscovery`:
    - pending goal edit
    - saved goal details
    - saved goal edit form

### Validation
- Backend compile: `./.venv/bin/python -m py_compile backend/db/schema.py backend/main.py backend/agent/goal_discovery.py` ✅
- Frontend build: `npm run build` ✅

### Files Modified
- `backend/db/schema.py`
- `backend/main.py`
- `backend/agent/goal_discovery.py`
- `frontend/src/api.ts`
- `frontend/src/components/tabs/Metas.tsx`
- `frontend/src/components/GoalDiscovery.tsx`

---

## 2026-04-07: Metas Graph Side Card — Editable Node Card + Editable Relations

### Problem Statement
After adding the graph visualizer in `Metas`, users needed to inspect and edit a selected node directly beside the graph, including hierarchy and relationship management, without switching to the discovery modal.

### What Changed
- **Two-panel graph area in `Metas`:**
  - Converted visualizer section into a 2-column layout on wide screens:
    - left: graph canvas
    - right: selected-node card
  - Nodes are now clickable and selection is highlighted in the graph.
- **Editable node card (right panel):**
  - Added edit mode for full node fields (title, description, why, domains/tags, horizon, date, status/progress, motivation, scoring fields, JSON fields).
  - Added save flow using `updateGoal(...)`.
  - Added node deletion from the side card.
- **Editable hierarchy + relations in `Metas`:**
  - Added parent selector (`parent_goal_id`) to rewire hierarchy.
  - Added create relation form (target, type, note) via `createGoalRelation(...)`.
  - Added relation list with delete action for explicit relations via `deleteGoalRelation(...)`.
  - Kept category semantics and colors (`dependence`, `affinity`, `conflict`) visible in relation cards.

### Validation
- Frontend compile/build: `npm run build` ✅

### Files Modified
- `frontend/src/components/tabs/Metas.tsx`

---

## 2026-04-07: Goal Graph Hierarchy Layout + Child-Based Node Coloring + Metas Tab Visualizer

### Problem Statement
Goal nodes were floating without a clear top-down hierarchy, node color did not reflect graph structure, and the `Metas` tab lacked an embedded graph view above the goals list.

### What Changed
- **Discovery graph layout (`GoalDiscovery.tsx`):**
  - Added hierarchy depth computation from `parent_child` edges.
  - Updated node placement and force simulation to bias vertical position by depth:
    - parent nodes are pulled upward
    - child nodes are pulled downward by level
- **Child-count visual encoding:**
  - Added child-count computation for saved nodes.
  - Node fill color now scales by number of children (pending nodes remain distinct).
- **Metas tab graph visualizer (`Metas.tsx`):**
  - Added a compact graph visualizer section above the goals list.
  - Visualizer uses top-down hierarchical layout and child-count-based node coloring.
  - Edges are rendered with existing semantic colors (dependence/affinity/conflict).
  - Visualizer respects currently visible filtered goals (status/domain/horizon).

### Validation
- Frontend compile/build: `npm run build` ✅

### Files Modified
- `frontend/src/components/GoalDiscovery.tsx`
- `frontend/src/components/tabs/Metas.tsx`

---

## 2026-04-07: Goal Graph Editing QoL — Full Card Editing + No Reload on Non-Relationship Edits + Deleted Node Suppression

### Problem Statement
Users could edit hierarchy/relationships but needed full field editing directly from node cards. Also, non-relationship edits were triggering unnecessary full graph reloads, and previously deleted goals could reappear as pending nodes from historical extraction state.

### What Changed
- **Goal card editing (frontend discovery panel):**
  - Expanded pending-node card to allow editing each extracted field before saving.
  - Saved-node card now includes direct delete action (`Eliminar nodo`) and keeps full field editor available.
- **No full graph reload for non-relationship edits:**
  - Saving edits to regular goal fields now patches local node state (`savedGoals`) in-place.
  - Removed `loadGraph()` dependency from non-relationship save path.
- **Deleted-node resurrection prevention:**
  - Added suppressed fingerprint state to prevent dismissed/deleted goals from reappearing as pending nodes.
  - On resume, discovery now avoids rehydrating entire historical `extracted_goals` list ("no conversation rescan from now on"), and only accepts new extracted goals from subsequent turns.
  - Deleting a saved node now removes local nodes/edges immediately and suppresses matching pending candidates.
- **Batch/pending save UX improvement:**
  - Saving pending goals now updates local graph nodes immediately without full fetch.

### Validation
- Frontend compile/build: `npm run build` ✅

### Files Modified
- `frontend/src/components/GoalDiscovery.tsx`

---

## 2026-04-07: Discovery Output Contract Tightening — Force Explicit Goal Block Open/Close Tags

### Problem Statement
Discovery responses sometimes used markdown headings like `**META IDENTIFICADA 1**` instead of bracket tags, causing goals to fail extraction and not appear as pending nodes.

### What Changed
- Strengthened `GOAL_DISCOVERY_PROMPT` in `backend/agent/goal_discovery.py` with explicit hard requirements:
  - each goal must start with `[META_IDENTIFICADA]`
  - each goal must end with `[/META_IDENTIFICADA]`
  - explicitly forbids alternate formats (`**META IDENTIFICADA**`, numbered markdown headers, etc.)
- Added parser fallback to recognize numbered markdown variants (`**META IDENTIFICADA 1**`) as a safety net while prompt adherence improves.

### Validation
- Parser test with two numbered markdown blocks now extracts two goals successfully ✅
- Backend compile: `python -m py_compile backend/agent/goal_discovery.py` ✅

### Files Modified
- `backend/agent/goal_discovery.py`

---

## 2026-04-07: Goal Extraction Robustness — Support `**META IDENTIFICADA**` Format

### Problem Statement
Some discovery responses used markdown heading format (`**META IDENTIFICADA**`) instead of bracket tags (`[META_IDENTIFICADA]`), so pending nodes were not created even when the goal payload text was present.

### What Changed
- Enhanced extraction in `backend/agent/goal_discovery.py` to parse both:
  - `[META_IDENTIFICADA] ... [/META_IDENTIFICADA]`
  - `**META IDENTIFICADA**` blocks (including missing explicit closing tag)
- Added robust segment parsing with span tracking, so goal field blocks are extracted while preserving trailing conversational text.
- Improved field normalization:
  - tolerant key normalization (markdown/bold/accents)
  - Spanish horizon aliases (`mensual`, `trimestral`, etc.) -> canonical values
  - motivation aliases and parenthetical variants (e.g., `external (...)`)
- Updated cleanup to remove structured goal blocks from visible reply without deleting the rest of Nash’s message.

### Validation
- Parsed real user-style sample (`**META IDENTIFICADA**`, no closing tag, `8/10`, trailing follow-up question) successfully ✅
- Backend compile: `python -m py_compile backend/agent/goal_discovery.py` ✅

### Files Modified
- `backend/agent/goal_discovery.py`

---

## 2026-04-07: Goal Discovery Prompt Retune — More Directive, Faster V1 Goal Creation

### Problem Statement
Discovery conversation in `Explorar Metas` was too open-ended and exploratory, which made it hard to create an initial goal set quickly from zero.

### What Changed
- Retuned `GOAL_DISCOVERY_PROMPT` in `backend/agent/goal_discovery.py` to a more action-oriented style:
  - explicit **iteración rápida** mode (`borrador v1 -> refinar -> confirmar`)
  - prioritize immediate goal extraction over prolonged open questioning
  - enforce concise turns and maximum one short question per turn
  - push close-ended option questions (A/B/C, ranking, horizon selection)
  - explicit behavior when user asks to create 2-3 goals in same turn
  - startup guidance now biases toward creating first concrete goals quickly
- Reduced discovery model temperature from `0.3` to `0.2` for steadier, more structured behavior.

### Validation
- Backend compile: `python -m py_compile backend/agent/goal_discovery.py` ✅

### Files Modified
- `backend/agent/goal_discovery.py`

---

## 2026-04-07: Goals Discovery UX Upgrade — Full Goal Editing, Batch Saves, Clickable Color-Coded Links, Multi-Domain Tags

### Problem Statement
`Explorar Metas` needed stronger authoring controls and graph clarity: users wanted to edit complete goal payloads, save multiple extracted goals quickly, understand relationships visually, and preserve multi-domain tags like `career|music|artificial_intelligence`.

### What Changed
- **Backend goals model (`backend/db/schema.py`):**
  - Added `goals.domain_tags_json` (migration-safe) for multi-domain tags.
  - Added normalization helpers to expose parsed `domain_tags` in API responses.
  - `insert_goal(...)` now accepts `domain_tags` and persists tags + primary domain.
  - `update_goal(...)` now accepts `domain_tags` updates and keeps tag/domain consistency.
  - Graph nodes now return parsed `domain_tags`.
- **Goal discovery extraction (`backend/agent/goal_discovery.py`):**
  - Prompt now explicitly supports generating 2-3 goals in one response (one block each).
  - `dominio` parsing now supports multi-tag strings and stores `domain_tags`.
  - Added display fallback when response text is empty after block stripping so Nash message is always visible.
- **Goal creation API (`backend/main.py`):**
  - `POST /api/goals` now accepts `domain_tags`.
- **Frontend goal discovery UI (`frontend/src/components/GoalDiscovery.tsx`):**
  - Added **Edit** mode for saved goals with full-field form (title, description, why, status, progress, motivation, scores, JSON fields, tags, etc.).
  - Added batch save controls: **Guardar 2 metas**, **Guardar 3 metas**, **Guardar todas**.
  - Edge lines are now **clickable**, **color-coded by category**:
    - Dependencia (parent/depends_on) → blue
    - Afinidad (synergy/supports/related) → green
    - Conflicto (conflicts_with/blocks) → red
  - Added selected-edge detail card and kept per-node relation details.
  - Pending/saved cards now show richer goal fields.
- **Frontend API typing (`frontend/src/api.ts`):**
  - Extended `Goal` and goal update/create payload types with advanced fields and `domain_tags`.

### Validation
- Backend compile: `python -m py_compile backend/db/schema.py backend/agent/goal_discovery.py backend/main.py` ✅
- Frontend build: `npm run build` ✅
- Parser smoke test with 2 malformed/multi-tag blocks succeeds ✅

### Files Modified
- `backend/db/schema.py`
- `backend/agent/goal_discovery.py`
- `backend/main.py`
- `frontend/src/components/GoalDiscovery.tsx`
- `frontend/src/api.ts`

---

## 2026-04-07: Goal Discovery Parsing Hardening — Immediate Pending Goal Creation on Imperfect Blocks

### Problem Statement
In `Explorar Metas`, some model responses included `[META_IDENTIFICADA]` blocks with formatting issues (for example: missing closing tag, enum fields with multiple options like `career|music|...`, numeric values like `8/10`). Those turns looked valid to users but no pending goal node/card was created.

### What Changed
- Updated `backend/agent/goal_discovery.py` extraction to accept:
  - missing closing tag (`[/META_IDENTIFICADA]`) by parsing until end-of-message
  - case-insensitive block tags
  - numeric fields from formats like `8/10` (takes first integer)
  - enum fields (`domain`, `horizon`, `motivacion`) when model emits multiple options separated by `|` or `,` (selects first valid value)
  - invalid placeholder date strings are normalized to `None`
- Updated display cleanup to remove malformed goal blocks even without closing tags, preventing raw extraction markup from leaking into the chat bubble.

### Validation
- Replayed a real stored malformed response from `goal_discovery_sessions.id=6`.
- Parser now extracts one structured goal successfully and cleans block text from display ✅

### Files Modified
- `backend/agent/goal_discovery.py`

---

## 2026-04-07: ASR Runtime Finalization — Local Parakeet Path Default + Py3.13-Compatible Dependency Set

### Problem Statement
After downloading `nvidia/parakeet-tdt-0.6b-v3` locally, runtime needed to prefer local model usage by default and avoid `nemo_toolkit[asr]` installation failures on Python 3.13 (`kaldialign` wheel mismatch).

### What Changed
- Updated default `ASR_MODEL` in `backend/config.py` to local path:
  - `~/.nash/models/parakeet-tdt-0.6b-v3`
- Kept `ASR_BACKEND=auto` so TDT models resolve to NeMo path automatically.
- Updated `requirements.txt`:
  - replaced `nemo_toolkit[asr]` with `nemo_toolkit>=2.7.0`
  - added explicit NeMo companion dependencies and `kaldialign>=0.9.3` for Python 3.13 compatibility.
- Updated docs/context files to reflect local-path default and final ASR setup.
- Verified local transcription works with:
  - `ASR_MODEL=~/.nash/models/parakeet-tdt-0.6b-v3`
  - `ASR_BACKEND=nemo`

### Validation
- Backend compile: `python -m py_compile backend/config.py backend/audio/transcriber.py backend/main.py` ✅
- Local short-audio transcription completed successfully and produced expected Spanish output ✅

### Files Modified
- `backend/config.py`
- `requirements.txt`
- `ENVIRONMENT.md`
- `CONTEXT_HANDOFF.md`
- `nash_life_manager_plan.md`

---

## 2026-04-06: ASR Follow-up — Default Model Corrected to `nvidia/parakeet-tdt-0.6b-v3` + NeMo Backend Support

### Problem Statement
The initially configured model id (`nvidia/parakeet-ctc-0.6b-es`) was not available on Hugging Face. A valid replacement was found: `nvidia/parakeet-tdt-0.6b-v3`.

### What Changed
- Updated default `ASR_MODEL` in `backend/config.py` to:
  - `nvidia/parakeet-tdt-0.6b-v3`
- Added `ASR_BACKEND` config (`auto|nemo|transformers`) for explicit runtime control.
- Extended `backend/audio/transcriber.py` to support two runtime paths:
  - **NeMo backend** for TDT / `.nemo` models (default path for the new model).
  - **Transformers backend** for CTC/Transformers-compatible ASR models.
- Added automatic backend selection in `auto` mode.
- Added non-WAV audio conversion for NeMo path (webm -> mono 16k wav temp file).
- Added NeMo dependency in `requirements.txt`:
  - `nemo_toolkit[asr]>=2.7.0`
- Updated docs/plans to reflect new default model and backend behavior.

### Validation
- Backend compile: `python -m py_compile backend/audio/transcriber.py backend/config.py backend/main.py` ✅
- Hub checks:
  - `nvidia/parakeet-tdt-0.6b-v3` reachable ✅
  - dry-run download succeeds ✅

### Files Modified
- `backend/config.py`
- `backend/audio/transcriber.py`
- `requirements.txt`
- `ENVIRONMENT.md`
- `CONTEXT_HANDOFF.md`
- `nash_life_manager_plan.md`

---

## 2026-04-06: ASR Migration — MLX Whisper → NVIDIA Parakeet (`nvidia/parakeet-ctc-0.6b-es`)

### Problem Statement
Transcription quality for Spanish with occasional English words needed improvement, and the project was still tied to an older MLX-Whisper stack.

### What Changed
- Replaced MLX-Whisper transcription backend with Transformers ASR in `backend/audio/transcriber.py`.
- New ASR config in `backend/config.py`:
  - `ASR_MODEL` defaults to `"nvidia/parakeet-ctc-0.6b-es"` and supports env override (`ASR_MODEL`) for HF id or local model path
  - `ASR_HF_TOKEN` (from `HF_TOKEN` / `HUGGINGFACE_HUB_TOKEN`, optional for gated repos)
  - `ASR_CHUNK_LENGTH_S = 30`
  - `ASR_STRIDE_LENGTH_S = 5`
- Implemented one-time lazy model loading with device selection:
  - CUDA (`float16`) when available
  - MPS/CPU (`float32`) otherwise
- Added chunked inference for long recordings to reduce memory spikes and improve stability on long uploads.
- Added explicit gated-model handling:
  - clear runtime error when Hugging Face returns 401
  - guidance to set token or use a local/public model path
- Updated Python dependencies in `requirements.txt`:
  - removed `mlx-whisper`
  - added `torch`, `transformers`, `sentencepiece`
- Updated environment/context docs to reflect Parakeet as the canonical ASR model.

### Validation
- Backend compile: `python -m py_compile backend/audio/transcriber.py backend/config.py backend/audio/ingest.py` ✅

### Files Modified
- `backend/audio/transcriber.py`
- `backend/config.py`
- `requirements.txt`
- `ENVIRONMENT.md`
- `CONTEXT_HANDOFF.md`
- `nash_life_manager_plan.md`

---

## 2026-04-06: Reply Stream Hardening — Ignore Tool JSON as Final Nash Message

### Problem Statement
After switching to DeepSeek-V3.2, some turns ended with tool-call JSON payload text stored/displayed as `nash_response` instead of a user-facing assistant reply.

### What Changed
- Added robust assistant-response extraction in `backend/main.py`:
  - `_content_to_text(...)`
  - `_looks_like_tool_payload(...)`
  - `_pick_user_facing_response(...)`
- Audio and text chat streams now:
  - Prefer last valid assistant text message.
  - Skip content that looks like raw tool JSON (`{"name":"...","parameters":...}`).
  - Use a short fallback response when no valid assistant text exists.
- Added warning logs when fallback is used:
  - `response_fallback_used`
  - `chat_response_fallback_used`
- Added Whisper language toggle in config/transcriber:
  - `WHISPER_FORCE_LANGUAGE = False` by default (auto-detect).
  - When set to `True`, transcription uses `WHISPER_LANGUAGE` (currently `es`).

### Validation
- Backend compile: `python -m py_compile backend/main.py` ✅

### Files Modified
- `backend/main.py`
- `backend/config.py`
- `backend/audio/transcriber.py`

---

## 2026-04-06: Goal Graph V1 — Hierarchy + Relations + Discovery Split View

### Problem Statement
The goals flow could extract/save goals from conversation, but it could not model relationships between goals, visualize goal graphs, or edit hierarchy from the discovery UI.

### What Changed

**Backend graph model (`backend/db/schema.py`):**
- Added `goals.parent_goal_id` (self-reference for hierarchy nesting).
- Added `goal_relations` table for directed non-hierarchical edges:
  - `related`, `supports`, `depends_on`, `conflicts_with`, `synergy`, `blocks`.
- Added migration-safe schema updates + indexes for parent and relation lookups.
- Added graph helpers:
  - `get_goals_graph()`
  - `insert_goal_relation()`
  - `delete_goal_relation()`
- Updated goal CRUD:
  - `insert_goal(..., parent_goal_id=...)`
  - `update_goal(...)` supports `parent_goal_id` validation.
  - `delete_goal(...)` now clears hierarchy/relation references safely.

**Backend API (`backend/main.py`):**
- Added `GET /api/goals/graph`
- Added `POST /api/goals/relations`
- Added `DELETE /api/goals/relations/{relation_id}`
- `POST /api/goals` now accepts `parent_goal_id`.
- `PATCH /api/goals/{id}` now returns clear validation errors for invalid parent updates.

**Frontend API + UI (`frontend/src/api.ts`, `frontend/src/components/GoalDiscovery.tsx`):**
- Added graph/relation API client methods:
  - `fetchGoalsGraph()`
  - `createGoalRelation()`
  - `deleteGoalRelation()`
- Extended `Goal` type with `parent_goal_id`.
- Reworked `Explorar Metas` right panel into a split layout:
  - Top: floating force-directed goal graph (saved + pending nodes).
  - Bottom: node details editor.
- Clicking a node now shows detail fields and actions:
  - Pending node: save/discard.
  - Saved node: set parent, create relation, delete relation edges.

### Validation
- Backend compile: `python -m py_compile backend/main.py backend/db/schema.py backend/agent/goal_discovery.py` ✅
- Frontend build: `npm run build` ✅

### Risks / Follow-up

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Parent cycle prevention is minimal (self-check only) | Medium | Add full cycle detection before parent assignment |
| Graph can become dense/noisy with many nodes | Medium | Add filters, clustering, and zoom controls in next iteration |
| Discovery pending list may still need richer dedupe logic | Low/Medium | Add server-side pending goal IDs in future |

### Files Modified

| File | Change |
|------|--------|
| `backend/db/schema.py` | Added hierarchy + relation schema, graph helpers, CRUD updates |
| `backend/main.py` | Added goals graph/relation endpoints and parent support |
| `frontend/src/api.ts` | Added graph/relation API wrappers and `parent_goal_id` typing |
| `frontend/src/components/GoalDiscovery.tsx` | Added floating graph + split node detail editor |

---

## 2026-04-06: Ollama Model Migration — Qwen 2.5 → DeepSeek-V3.2 (Local)

### Problem Statement
Current app-wide LLM usage was configured around Qwen 2.5 generation. User requested migration to a newer local model for stronger reasoning and output quality.

### What Changed

**App model config (`backend/config.py`):**
- `OLLAMA_MODEL` changed from `qwen2.5:7b` to `drivedenpadev/deepseek-v3.2`
- `OLLAMA_SYNTH_MODEL` changed from `qwen2.5:14b` to `drivedenpadev/deepseek-v3.2`
- `OLLAMA_EMBED_MODEL` remains `nomic-embed-text` (no change)

**UI and docs alignment:**
- Dev tab model label updated to `drivedenpadev/deepseek-v3.2`
- Runtime/setup docs updated in `ENVIRONMENT.md`
- Context docs updated in `CONTEXT_HANDOFF.md`
- Architecture shorthand updated in `nash_life_manager_plan.md`

### Why This Design

| Decision | Rationale |
|----------|-----------|
| Single-model switch first | Fastest safe migration path with minimal code churn |
| Keep embeddings unchanged | Retrieval stack already tuned to `nomic-embed-text` |
| Keep `OLLAMA_SYNTH_MODEL` in config | Preserves future split-model option without refactor |

### Risks / Follow-up

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Behavior drift in prompts/tools | Medium | Validate key flows (chat, discovery, question generation, synthesis) |
| Latency/cost changes on local hardware | Medium | Track response times and tune `num_ctx`/temperature if needed |
| Dev tab label mismatch in future | Low | Consider exposing model name from backend health/config endpoint |

### Files Modified

| File | Change |
|------|--------|
| `backend/config.py` | Switched default Ollama model constants |
| `frontend/src/components/tabs/Dev.tsx` | Updated displayed model name |
| `ENVIRONMENT.md` | Updated required model + pull command |
| `CONTEXT_HANDOFF.md` | Updated model references/checklist |
| `nash_life_manager_plan.md` | Updated architecture shorthand |

---

## 2026-04-05: Phase 5/6 Iterative V1 — Cuerpo + Dinero Live

### Problem Statement
The schema and discovery engine for Nutrition, Exercise, and Finance existed, but users still saw placeholders in the UI for `Cuerpo` and `Dinero`. There was no end-to-end way to use the new module data from the web app.

### What We Implemented

**Backend completion (`backend/main.py`):**
- Added module discovery endpoints for `nutrition`, `exercise`, `finance`:
  - `POST /api/{module}/discovery/start`
  - `GET /api/{module}/discovery/active`
  - `GET /api/{module}/discovery/{id}`
  - `POST /api/{module}/discovery/{id}/chat`
  - `POST /api/{module}/discovery/{id}/end`
- Added Nutrition APIs:
  - `GET/PATCH /api/nutrition/profile`
  - `GET/POST /api/nutrition/entries`
- Added Exercise APIs:
  - `GET/PATCH /api/exercise/profile`
  - `GET/POST /api/exercise/templates`
  - `GET/POST /api/exercise/sessions`
- Added Finance APIs:
  - `GET/PATCH /api/finance/profile`
  - `GET /api/finance/categories`
  - `GET/POST /api/finance/expenses`
  - `GET /api/finance/summary`

**Frontend completion:**
- `frontend/src/api.ts`
  - Added full Phase 5/6 typed API client layer (module discovery + nutrition + exercise + finance).
- `frontend/src/components/ModuleDiscovery.tsx` (NEW)
  - Reusable full-screen discovery chat modal used by modules.
- `frontend/src/components/tabs/Cuerpo.tsx` (NEW)
  - Nutrition view: daily totals, protein progress, quick food logging, recent food list.
  - Exercise view: profile summary, quick session logging (minimum/optimal), recent sessions.
  - Discovery entry points for Nutrition and Exercise.
- `frontend/src/components/tabs/Dinero.tsx` (NEW)
  - Finance summary by month/category, quick expense form, recent expenses.
  - Discovery entry point for Finance.
- `frontend/src/App.tsx`
  - Unlocked `Cuerpo` and `Dinero` tabs and mounted real components.

### Validation
- Backend compile: `python -m py_compile backend/main.py backend/db/schema.py backend/agent/module_discovery.py` ✅
- Frontend build: `npm run build` ✅

### Why This Design

| Decision | Rationale |
|----------|-----------|
| Reusable module discovery modal | Avoid duplicated chat logic across tabs |
| V1 focuses on fast forms + summaries | Matches iterative goal: usable now, depth later |
| Separate API wrappers with strict TS types | Keeps tab logic simpler and safer to evolve |
| Keep advanced features as follow-up | Enables shipping quickly without blocking on perfect UX |

### What Could Go Wrong

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Discovery extraction quality varies by prompt | Medium | Keep profile update visible; iterate prompt/parser with real logs |
| Missing macro auto-estimation in UI flow | Medium | Add audio + estimation pipeline in next Body iteration |
| Finance strategy depth (debt planning) still shallow | Medium | Add avalanche/snowball projections in next iteration |
| Slow Ollama responses on discovery/generation | Medium | Add stronger loading states/timeouts and retry UX |

### Files Created/Modified

| File | Change |
|------|--------|
| `backend/main.py` | Added full Phase 5/6 API surface |
| `frontend/src/api.ts` | Added Phase 5/6 API types and functions |
| `frontend/src/components/ModuleDiscovery.tsx` | **NEW** reusable module discovery chat |
| `frontend/src/components/tabs/Cuerpo.tsx` | **NEW** nutrition + exercise tab |
| `frontend/src/components/tabs/Dinero.tsx` | **NEW** finance tab |
| `frontend/src/App.tsx` | Wired `Cuerpo` and `Dinero` tabs |
| `nash_life_manager_plan.md` | Updated phase status and next iteration backlog |
| `CONTEXT_HANDOFF.md` | Updated current state and follow-up priorities |

---

## 2026-04-05: Goal Discovery Conversation System

### Problem Statement
User wants to explore goals through conversation with Nash rather than filling forms manually. Goals should emerge from natural dialogue where Nash asks questions, understands context, detects conflicts, and gives opinions.

### Research Conducted
See `docs/goal_discovery_research.md` for full synthesis including:
- **GROW Model** — Goal, Reality, Options, Will coaching framework
- **Motivational Interviewing (OARS)** — Open questions, Affirmations, Reflections, Summaries
- **Goal Systems Theory** — Coherence, conflict, multifinality (Kruglanski et al.)
- **Goal Attributes** — Importance, difficulty, commitment, specificity (Locke & Latham)
- **LLM Goal Setting Architecture** — State-based conversation flow (arXiv paper)

### What We Implemented

**Database Schema (backend/db/schema.py):**
```sql
-- New goal fields for discovery
ALTER TABLE goals ADD COLUMN importance INTEGER CHECK (importance BETWEEN 1 AND 10);
ALTER TABLE goals ADD COLUMN difficulty INTEGER CHECK (difficulty BETWEEN 1 AND 10);
ALTER TABLE goals ADD COLUMN commitment INTEGER CHECK (commitment BETWEEN 1 AND 10);
ALTER TABLE goals ADD COLUMN specificity INTEGER CHECK (specificity BETWEEN 1 AND 10);
ALTER TABLE goals ADD COLUMN locus_of_control TEXT;
ALTER TABLE goals ADD COLUMN nash_opinion TEXT;
ALTER TABLE goals ADD COLUMN coherence_score REAL;
ALTER TABLE goals ADD COLUMN conflicts_json TEXT;
ALTER TABLE goals ADD COLUMN synergies_json TEXT;
ALTER TABLE goals ADD COLUMN priority_rank INTEGER;
ALTER TABLE goals ADD COLUMN source TEXT DEFAULT 'manual';
ALTER TABLE goals ADD COLUMN discovery_session_id INTEGER;

-- Discovery sessions table
CREATE TABLE goal_discovery_sessions (
    id, started_at, ended_at, status, current_state,
    messages_json, extracted_goals_json, context_snapshot,
    goals_confirmed, summary
);
```

**Goal Discovery Agent (backend/agent/goal_discovery.py):**
- Specialized system prompt combining GROW + MI principles
- Context injection: self_profile + profile_summaries + existing goals + domain ratings
- Goal extraction via `[META_IDENTIFICADA]...[/META_IDENTIFICADA]` blocks
- Coherence analysis and Nash opinion generation

**API Endpoints (backend/main.py):**
- `POST /api/goals/discovery/start` — Start or resume discovery session
- `GET /api/goals/discovery/active` — Get current active session
- `POST /api/goals/discovery/{id}/chat` — Send message (text or audio)
- `POST /api/goals/discovery/save` — Confirm and save extracted goal
- `POST /api/goals/discovery/{id}/end` — End session

**Frontend (GoalDiscovery.tsx):**
- Full-screen conversation UI with chat interface
- Voice input support (audio recording)
- Side panel showing extracted goals
- Confirm/discard extracted goals before saving
- Real-time session stats

**Metas Tab Integration:**
- "Explorar Metas" button with chat icon
- Opens full-screen discovery modal

### Why This Design

| Decision | Rationale |
|----------|-----------|
| GROW + MI hybrid | Combines proven coaching frameworks for natural discovery |
| Large context (16K) | Discovery conversations need full history for coherence |
| Goal extraction in-line | Nash identifies goals naturally during conversation |
| Pending goals sidebar | User can review and confirm before saving |
| Nash opinion field | Provides value beyond simple goal tracking |
| Session persistence | Can resume discovery conversation later |

### Goal Attributes Added (Research-Based)

| Attribute | Source | Purpose |
|-----------|--------|---------|
| importance | Locke & Latham | Predicts commitment and persistence |
| difficulty | Locke & Latham | Optimal challenge level |
| commitment | Locke & Latham | Strongest predictor of success |
| specificity | Goal research | Specific > vague for performance |
| nash_opinion | Custom | Nash's analysis of coherence, realism |
| coherence_score | GST | How well goal fits with system |

### Files Created/Modified

| File | Change |
|------|--------|
| `docs/goal_discovery_research.md` | **NEW** — Research synthesis |
| `backend/db/schema.py` | +12 goal columns, +1 table, migration, helpers |
| `backend/agent/goal_discovery.py` | **NEW** — Discovery conversation engine |
| `backend/main.py` | +6 API endpoints |
| `frontend/src/api.ts` | +7 API functions, types |
| `frontend/src/components/GoalDiscovery.tsx` | **NEW** — Full discovery UI |
| `frontend/src/components/tabs/Metas.tsx` | Added discovery button + integration |

### What Could Go Wrong

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| LLM doesn't extract goals properly | Medium | Clear format instructions + parser handles variations |
| Conversations get too long | Low | 16K context + can end session anytime |
| Nash gives bad advice | Medium | User must confirm goals before saving |
| Audio transcription errors | Low | Same transcription system as main app |
| Goals extracted don't match user intent | Medium | Pending list lets user review + discard |

### Future Enhancements (Lined Up)

1. **Voice output for Nash** — TTS for natural conversation
2. **Expert panel debate** — 5 "experts" analyze goals from different perspectives
3. **MCP integration** — Specialized coaching tools
4. **Coherence visualization** — Graph of goal relationships
5. **Weekly review integration** — Connect discovery to regular check-ins

### Success Metrics

- [ ] User can start conversation and explore goals naturally
- [ ] Nash extracts goals with all required fields
- [ ] Nash provides useful opinions on coherence and priorities
- [ ] Extracted goals can be confirmed and saved
- [ ] Voice input works for conversation
- [ ] Session can be resumed if interrupted

---

## 2026-04-05: Phase 3b-3f — Detailed Implementation Plans

### What Was Done

Added comprehensive implementation plans for the remaining goals phases to `nash_life_manager_plan.md`:

| Phase | Focus | Key Components |
|-------|-------|----------------|
| **3b** | Goal Hierarchy + OKRs | `parent_goal_id`, `key_results` table, progress auto-calculation |
| **3c** | Self-Concordance | Concordance scoring (0-100), conflict detection, review system |
| **3d** | Implementation Intentions | "If-then" planning, cue types (time/location/event/emotion/action), trigger logging |
| **3e** | Time Blocking | Calendar view, `time_blocks` table, recurrence, actual vs planned tracking |
| **3f** | Intelligent Features | Smart suggestions, weekly review, progress predictions, coherence map |

### Database Schema Additions Planned

**Phase 3b:**
- `goals.parent_goal_id` — Self-referential FK for hierarchy
- `key_results` — OKR-style measurable outcomes (number, percentage, boolean, milestone types)

**Phase 3c:**
- `goals.concordance_score` — Calculated alignment score
- `goals.values_alignment` — JSON of matched core values
- `concordance_reviews` — History of motivation check-ins

**Phase 3d:**
- `implementation_intentions` — If-then plans with cue types
- `intention_logs` — Track when intentions trigger and follow-through

**Phase 3e:**
- `time_blocks` — Calendar slots with recurrence, actual time tracking

### Key Algorithms Designed

1. **Progress Calculation** — Auto-calculate goal progress from key results (completion %) and/or child goals (avg progress)

2. **Concordance Scoring** — 0-100 scale based on:
   - Motivation type (external→intrinsic: 10-40 pts)
   - Why_matters quality (0-30 pts)
   - Values alignment (0-30 pts)

3. **Conflict Detection** — Identify competing goals by:
   - Time constraints
   - Financial requirements
   - Value misalignment
   - Deadline clustering

### Why This Structure

| Decision | Rationale |
|----------|-----------|
| Phase increments | Ship value incrementally; don't over-engineer before testing |
| Key Results as separate table | Flexible metric types; one goal can have 0-n KRs |
| Concordance scoring | Quantifies self-alignment for prioritization |
| Implementation intentions as first-class entity | Research shows 2-3x success rate; deserves dedicated tracking |
| Time blocks separate from goals | Block can exist without goal (meetings, etc.); flexible |

### Implementation Order Rationale

1. **3b first** — Hierarchy is foundational; needed for proper goal organization
2. **3c second** — Concordance scoring uses hierarchy to detect conflicts
3. **3d third** — Implementation intentions work best with clear goal structure
4. **3e fourth** — Time blocking benefits from knowing which goals to schedule
5. **3f last** — Intelligent features need all other data to provide value

### Files Updated

| File | Change |
|------|--------|
| `nash_life_manager_plan.md` | Added ~300 lines of detailed phase specs |

---

## 2026-04-04: Phase 3a — Goals Foundation Implementation

### Problem Statement
User wants to start tracking goals with a Wheel of Life approach, domain-based organization, and self-concordance awareness.

### What Was Before
- "Metas" tab was locked/placeholder
- No goals infrastructure in database
- No way to track life domain satisfaction over time

### What We Implemented

**Database (backend/db/schema.py):**
```sql
-- Life domains (Wheel of Life, 8 areas)
CREATE TABLE life_domains (
    id, code, name_es, description_es, icon, color, sort_order
);

-- Domain satisfaction tracking over time
CREATE TABLE domain_ratings (
    id, domain_id, rating (1-10), notes, rated_at
);

-- Goals with self-concordance support
CREATE TABLE goals (
    id, domain_id, title, description, why_matters,
    horizon (life/annual/quarterly/monthly/weekly),
    target_date, status, progress_pct, motivation_type,
    created_at, updated_at, completed_at
);
```

**Seeded domains:**
- Career, Finance, Health, Relationships, Personal Growth, Fun/Recreation, Environment, Contribution

**API endpoints (backend/main.py):**
- `GET /api/goals/domains` — List domains with latest ratings
- `POST /api/goals/domains/rate` — Bulk rate domains
- `GET /api/goals/domains/{code}/history` — Rating history
- `GET /api/goals` — List goals (with filters)
- `POST /api/goals` — Create goal
- `GET /api/goals/{id}` — Get single goal
- `PATCH /api/goals/{id}` — Update goal
- `DELETE /api/goals/{id}` — Delete goal
- `GET /api/goals/summary` — Stats summary

**Frontend (Metas.tsx):**
- Domain grid with color-coded ratings
- Rating modal with sliders
- Goals list with filters (status, horizon, domain)
- Create goal modal with self-concordance fields
- Progress tracking (+10%, Complete, Pause actions)

### Why This Design

| Decision | Rationale |
|----------|-----------|
| 8 Wheel of Life domains | Research-backed, covers major life areas |
| Domain ratings over time | Track progress, see trends |
| `why_matters` field | Self-concordance research shows this increases goal completion |
| `motivation_type` enum | SDT-based (external → intrinsic) for self-awareness |
| Horizon levels | Goal hierarchy research supports time-based organization |
| Progress percentage | Simple, visual, encourages small updates |

### Files Changed

| File | Change |
|------|--------|
| `backend/db/schema.py` | Added 3 tables, seeding function, 15+ helper functions |
| `backend/main.py` | Added 9 API endpoints, updated imports |
| `frontend/src/api.ts` | Added 10+ API functions, Goal/Domain types |
| `frontend/src/components/tabs/Metas.tsx` | **NEW** — Full goals tab (~450 lines) |
| `frontend/src/App.tsx` | Unlocked Metas tab, added import |

### What Could Go Wrong

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Goals without domains feel disconnected | Medium | Domain is optional, can be added later |
| Too many goals overwhelm user | Medium | Filters help, could add "focus" mode later |
| Domain ratings feel like a chore | Low | Only update when user wants, not forced |
| Progress tracking is too manual | Medium | Phase 3b will add key results for auto-calculation |
| No goal hierarchy yet | Expected | Phase 3b adds parent-child relationships |

### What's NOT Implemented (Phase 3b-3f)

- Goal hierarchy (parent-child)
- Key Results (OKR style)
- Implementation intentions (if-then)
- Time blocking
- Calendar integration
- Conflict detection
- Coherence scoring

### Success Metrics

- [ ] User can create and track goals
- [ ] Domain ratings update correctly
- [ ] Filters work as expected
- [ ] Self-concordance fields are being used
- [ ] UI is intuitive and not overwhelming

---

## 2026-04-04: QuestionEngine Redesign — Direct Questions

### Problem Statement
User reported "resistance to answer the Preguntas de hoy" because questions felt too vague and open-ended.

### What Was Before

**Previous question types (7 types, therapeutic-style):**
```python
QUESTION_TYPES = [
    "memory_archaeology",   # "¿Qué experiencia formativa recuerdas de...?"
    "exception",            # "¿Cuándo NO ocurre este problema?"
    "scaling",              # "Del 1 al 10..."
    "parts_work",           # "¿Qué parte de ti quiere X mientras otra quiere Y?"
    "behavioral_chain",     # "¿Qué pasó justo antes de que...?"
    "future_self",          # "¿Cómo te imaginas en 5 años...?"
    "contrast",             # "¿Qué diferencia hay entre X e Y para ti?"
]
```

**Previous prompt structure:**
- Long therapeutic framing
- Complex frameworks (MI, SFBT, IFS, ABC)
- Safety gating based on emotional state
- Questions designed for "deep reflection"

**Example generated questions (actual output from previous system):**
- "¿Qué patrones notas en cómo manejas el estrés laboral?"
- "¿Qué parte de ti quiere descansar mientras otra parte quiere ser productivo?"
- "¿Cuándo fue la última vez que sentiste que tu trabajo tenía significado profundo?"

### Why It Didn't Work

1. **High cognitive load**: Open-ended questions about "patterns" or "parts" require significant mental effort
2. **Abstract framing**: Questions about "meaning" or "patterns" feel like homework, not discovery
3. **Therapeutic tone**: Feels like being in therapy, creates resistance in casual daily use
4. **Time investment unclear**: User doesn't know if answer will take 30 seconds or 10 minutes
5. **No easy wins**: Every question feels "heavy" — no quick dopamine hits

**User feedback:** "maybe because they are too vague or too open"

### What We Changed

**New question types (6 types, direct/concrete):**
```python
QUESTION_TYPES = [
    "scaling",           # Keep: "Del 1 al 10, ¿qué tan contento estás con tu trabajo?"
    "this_or_that",      # NEW: "¿Prefieres más tiempo o más dinero?"
    "last_instance",     # NEW: "¿Cuándo fue la última vez que te reíste mucho?"
    "quick_fact",        # NEW: "¿A qué hora te despiertas normalmente?"
    "single_most",       # NEW: "¿Cuál es tu mayor fuente de estrés?"
    "tomorrow_change",   # NEW: "¿Qué cambiarías de tu rutina mañana?"
]
```

**New prompt philosophy:**
- Questions must be answerable in <30 seconds
- Concrete over abstract (specific instances, not patterns)
- Binary choices reveal preferences without requiring explanation
- Facts are facts — no interpretation needed
- "Most important" forces prioritization without open-ended reflection

**Removed:**
- `memory_archaeology` — Too heavy, requires accessing old memories
- `exception` — Abstract SFBT concept, hard to understand
- `parts_work` — IFS terminology confusing for non-therapists
- `behavioral_chain` — Too analytical, feels like debugging yourself
- `future_self` — Often triggers anxiety about the future
- `contrast` — Abstract comparison, unclear what's being asked

- Emotional safety gating — All new types are emotionally safe
- Framework labels (MI, SFBT, IFS) — Replaced with simple category names

### Files Changed

| File | Change |
|------|--------|
| `backend/config.py:37-48` | New `QUESTION_TYPES` list, empty `UNSAFE_QUESTION_TYPES` |
| `backend/agent/question_engine.py:1-50` | New docstring, imports, `FRAMEWORK_MAP`, `QUESTION_TYPE_DESCRIPTIONS` |
| `backend/agent/question_engine.py:77-135` | Completely rewritten `GENERATE_PROMPT` |
| `backend/agent/question_engine.py:161-169` | Removed `check_emotional_safety()` function |
| `backend/agent/question_engine.py:230-310` | Simplified `generate_daily_questions()` — removed safety filtering |
| `frontend/src/components/QuestionCard.tsx:16-29` | Added `TYPE_LABELS` for user-friendly display |
| `frontend/src/components/QuestionCard.tsx:141-145` | Simplified type badge display |

### Why We Think This Will Work

1. **Research-backed**: SFBT scaling questions are called "workhorses" due to effectiveness
2. **Harvard study**: Talking about preferences (this-or-that) activates pleasure centers
3. **Forced-choice research**: Binary choices reduce cognitive load and social desirability bias
4. **Intake assessment best practices**: Direct, specific questions gather more useful data faster
5. **User psychology**: Quick wins build habit, heavy questions create avoidance

### What Could Go Wrong

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Questions feel too shallow | Medium | Monitor if profile/semantic data quality decreases. Can add 1 deeper question per day if needed. |
| LLM doesn't follow new format | Low | Prompt is explicit with examples. Parser already handles variations. |
| Old questions in DB have old types | Low | `TYPE_LABELS` includes legacy types as fallback. |
| User wants deeper questions sometimes | Medium | Could add "Quiero una pregunta profunda" button later. |
| Less semantic units extracted from short answers | Medium | Track `richness_score` over time. Short factual answers may need different decomposition. |
| "This or that" feels like a game, not self-discovery | Low | Follow-up in conversation can explore "why" that choice. |

### Rollback Plan

If this doesn't work:
1. Revert `backend/config.py` to restore old `QUESTION_TYPES`
2. Revert `backend/agent/question_engine.py` (git checkout)
3. Old questions in DB will still work with legacy `TYPE_LABELS`

### Success Metrics

- [ ] User actually answers questions (vs skipping/ignoring)
- [ ] Questions generate useful semantic units (check `daily_question_answers` join with `semantic_units`)
- [ ] No complaints about questions being "vague" or "heavy"
- [ ] Profile gaps fill faster than before

### Related Research

See `docs/question_engine_improved_research.md` for full research synthesis including:
- SFBT scaling questions (Sweet Institute, Universal Coach Institute)
- This-or-that preference signals (Science of People, Harvard 2012 study)
- Forced-choice psychology (ResearchGate, Kent Academic Repository)
- Intake assessment practices (Quenza, SimplePractice)

---

## 2026-04-04: Phase 3 Goals Research Completed

### Context
User requested deep research on goals organization before implementation.

### What Was Researched

1. **Goal Hierarchy Theory** — Superordinate vs subordinate goals
2. **Self-Concordance** — Aligning goals with intrinsic values
3. **Implementation Intentions** — "If-then" planning
4. **Personal OKRs** — Adapting business framework for life
5. **Wheel of Life** — Domain-based satisfaction tracking
6. **Intelligent Calendar** — AI-assisted time blocking

### Key Decisions Made

| Decision | Rationale |
|----------|-----------|
| Use goal hierarchy (parent-child) | Research shows both levels needed for long-term success |
| Track motivation type per goal | Self-concordance predicts goal completion and well-being |
| Include implementation intentions | Meta-analysis shows 2-3x success rate improvement |
| Wheel of Life for domains | Established coaching tool, provides structure |
| Phase implementation (3a-3f) | Avoid over-engineering, ship incrementally |

### Files Created

- `docs/phase3_goals_research.md` — Full research synthesis (~26KB)
- Updated `nash_life_manager_plan.md` — Phase 3 section expanded

### Implementation Not Started

This was research only. Implementation phases:
- 3a: Foundation (domains, basic goals)
- 3b: Hierarchy & OKRs
- 3c: Self-Concordance
- 3d: Implementation Intentions
- 3e: Time Blocking
- 3f: Intelligent Features

---

## 2026-04-03: Conversation Threads in Historial

### Problem Statement
After user records a diary entry and Nash responds, the response disappeared when navigating away. User wanted to:
1. See Nash's response persistently
2. Reply to Nash's response (continue the conversation)

### What Was Before
- `diary_entries` table had no `nash_response` column
- No way to continue conversation after initial exchange
- Response only shown during streaming, lost after

### What We Changed

**Database:**
```sql
-- Added to diary_entries
ALTER TABLE diary_entries ADD COLUMN nash_response TEXT;

-- New table
CREATE TABLE diary_conversations (
    id INTEGER PRIMARY KEY,
    diary_entry_id INTEGER REFERENCES diary_entries(id),
    messages_json TEXT DEFAULT '[]',  -- [{role, content, audio_path}, ...]
    message_count INTEGER DEFAULT 0,
    created_at TEXT,
    updated_at TEXT
);
```

**Limits:**
- Max 11 messages per conversation (1 initial + 5 user + 5 Nash)
- Prevents infinite loops, keeps conversations focused

**API:**
- `GET /api/diary/{id}/conversation` — Get conversation thread
- `POST /api/diary/{id}/reply` — Reply with text or audio

**Frontend:**
- Expandable "Respuesta de Nash" section in Historial
- Conversation thread display with role styling
- Mic button for voice replies
- Text input for typed replies

### Why This Design

| Choice | Rationale |
|--------|-----------|
| Separate table for conversations | Keeps diary_entries clean, JSON blob simpler than normalized messages |
| 11 message limit | Prevents runaway conversations, matches typical coaching exchange |
| Voice + text replies | Consistency with main input methods |
| Semantic decomposition on replies | Conversations are rich data, should feed into profile |

### What Could Go Wrong

| Risk | Status |
|------|--------|
| Messages JSON grows large | Mitigated by 11 message limit |
| Audio files accumulate | Same as main recordings, accepted |
| User expects real-time chat | Current design is async — could confuse |

---

## 2026-04-03: Recording Stop Fix

### Problem
When user pressed stop, recording continued briefly, capturing noise like "trtrtrtrt" at the end of transcripts.

### What Was Before
```typescript
// useAudioRecorder.ts
recorder.stop();  // Stop recorder first
recorder.stream.getTracks().forEach(t => t.stop());  // Then stop tracks
```

The `recorder.stop()` triggers `ondataavailable` which may include buffered audio captured between button press and track stop.

### What We Changed
```typescript
// Stop tracks IMMEDIATELY to prevent more audio capture
recorder.stream.getTracks().forEach(t => t.stop());
// Then stop recorder
recorder.stop();
```

### Why This Works
Stopping tracks first immediately cuts the microphone input. The recorder then processes only what was already buffered, without new noise.

### What Could Go Wrong
- Might cut off last fraction of speech — not observed in testing
- Browser compatibility — tested on Chrome/Safari, works

---

## Template for Future Changes

```markdown
## YYYY-MM-DD: [Change Title]

### Problem Statement
[What problem are we solving? Include user feedback if available.]

### What Was Before
[Code snippets, behavior description, or screenshots]

### Why It Didn't Work
[Root cause analysis — be specific]

### What We Changed
[Code snippets, file list, behavioral changes]

### Why We Think This Will Work
[Research, reasoning, precedent]

### What Could Go Wrong
[Risks table with likelihood and mitigation]

### Rollback Plan
[How to undo if needed]

### Success Metrics
[How do we know it worked?]
```
