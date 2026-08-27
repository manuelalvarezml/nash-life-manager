# Nash Life Manager — Context handoff for continued work

This file is **onboarding context** for continuing Nash in another environment (e.g. Claude Code in terminal). It summarizes what exists, decisions from conversation, recent changes, and what to build next. **Do not treat this as the full architecture spec** — see the linked plans below.

---

## Canonical plan references (read these for depth)

| File | Purpose |
|------|---------|
| **`nash_life_manager_plan.md`** | **Living plan** in-repo: current implementation status, phased roadmap, short architecture notes. Update this as you ship features. |
| **`nash_life_manager_plan_reference.md`** | Full export of the original Cursor plan (research validity, Meta layer, Work module, QuestionEngine taxonomy, data model detail, ~800 lines). |
| **`~/.cursor/plans/nash_life_manager_8cac366c.plan.md`** | Same long plan at original path (if present on this machine). |

---

## Product intent (from the user)

- **Nash**: Private, **local-first** AI “life manager” for **Manuel** (Apple M4, 16GB RAM). As of **July 25, 2026**, the reasoning layer is moving from Ollama to the OpenAI API while keeping storage, audio, ASR, checkpoints, and vector retrieval local.
- **As of August 27, 2026**, the Body module has a more serious workout engine: adherence-first hypertrophy planning, home/gym equipment awareness, fallback sessions, PR tracking, repeated body measurements, and workout-state injection into Nash's reasoning context.
- **Voice-first**: Primary input is Spanish speech; UI and Nash replies in **Spanish**. **No translation** of stored transcripts (nuance matters for psychological profiling). **English words** in speech are supported: ASR now defaults to local **NVIDIA Parakeet TDT v3** (`~/.nash/models/parakeet-tdt-0.6b-v3`) with multilingual support.
- **Deep profile over time**: Declared truths + cumulative behavioral evidence, weights, contradictions — not generic coaching.
- **Modular app**: Tabs for Home, Historial, “Lo que Nash sabe”, Sobre Mi, Metas, Cuerpo, Dinero, Dev (with Trabajo/Mente/Progreso still placeholder). Future: deeper nutrition/workout/finance, goals/calendar/time, work tracking, meta transparency.
- **Agent stack**: **LangGraph** ReAct (not Deep Agents) — predictable tools, SQLite-friendly. Default reasoning path now targets **OpenAI `gpt-5.6`**, with Ollama preserved as an optional fallback.
- **Design values**: Benign, no streak-shame, self-compassion over pile-ons; eventually **meta layer** (“why Nash asked this”, data gaps); research-informed habits/wellness where applicable.

---

## What is implemented today (high level)

### Backend (`backend/`)

- **FastAPI** (`main.py`): CORS, lifespan (dirs, logging, `init_db`, **audio migration**).
- **Config** (`config.py`): `REPO_ROOT`, `NASH_HOME` (`~/.nash`), **`AUDIO_DIR = REPO_ROOT / "data/audio"`**, `LEGACY_AUDIO_DIR = ~/.nash/audio`, separate **`CHECKPOINT_DB_PATH`** for LangGraph (avoid closing main DB).
- **SQLite** (`db/schema.py`): `diary_entries` (incl. `audio_path`, `duration_s`, summary), `memories`, `profile_summaries`, `profile_facts`, `insights`; helpers for insert/list/migration columns; **`link_audio_if_transcript_matches`**, **`get_registered_audio_basenames`**, **`apply_profile_summary_updates`**.
- **Audio** (`audio/`): `save_audio`, **NVIDIA Parakeet** transcribe (default local path `~/.nash/models/parakeet-tdt-0.6b-v3`, auto backend: NeMo or Transformers-compatible model path), NeMo long-audio chunks default to **120s** and continue from the timestamp of word **-15** from the previous chunk when word timestamps are available, **`brief_summary.py`** (short Spanish summary via local LLM), **`ingest.py`**: copy legacy → `data/audio`, ingest orphan audio files (transcribe + diary row), **audio extension filter** (skip `.gitignore`).
- **Agent** (`agent/`): `graph.py` (shared LLM gateway, SqliteSaver on open sqlite conn, `prompt` injects profile + onboarding), `prompts.py` (Spanish, tools, **do not re-`log_diary_entry` when system note says voice already saved**), `profile.py` (context from summaries + facts + **finance snapshot + workout/body snapshot**), tools: diary, memory, `log_profile_fact`, **`profile_synthesize.py`** (refresh domain summaries from recent diaries), **`semantic_decomposer.py`** (extracts structured units, stores in SQLite + Chroma).
- **Workout engine** (`exercise_engine.py`): deterministic planner for primary + fallback sessions, minimum/optimal mode selection, A/B full-body structures for home and gym, measurement protocol, adherence summaries, and dashboard assembly for the Body tab.
- **API highlights**:
  - `POST /api/audio/upload` — save file → transcribe → **brief summary** → **`insert_diary_entry`** with `data/audio/...` path + optional **`duration_s`** from form → SSE: transcript, **diary** event (id, summary, audio URL), then agent (human message includes system note).
  - `POST /api/chat` — text → agent stream.
  - `GET /api/diary` — rows enriched with **`audio_play_url`**.
  - `GET /api/profile` — summaries, facts (up to 200), memories (100), **`diary_highlights`** (25 recent).
  - `POST /api/profile/synthesize` — run **`synthesize_profile_from_diaries`** → **`apply_profile_summary_updates`**.
  - `GET /api/questions/today`, `POST /api/questions/generate`, `POST /api/questions/answer`, `GET /api/questions/stats`.
  - **Goals graph APIs (V1):** `GET /api/goals/graph`, `POST /api/goals/relations`, `DELETE /api/goals/relations/{id}`, plus `parent_goal_id` support in goal create/update.
  - **Phase 5 APIs (V1):** module discovery (`POST /api/{module}/discovery/start`, `POST /api/{module}/discovery/{id}/chat`, etc.), nutrition (`/api/nutrition/*`), exercise (`/api/exercise/*`), finance (`/api/finance/*`).
  - `GET /api/debug/last`, `GET /api/health`.
  - **Static**: `GET /media/audio/*` → `data/audio`.

### Frontend (`frontend/`)

- **Vite** proxies `/api` and **`/media`** to backend (default port **8002** in config; confirm `vite.config.ts`).
- **Tabs** (`App.tsx`): Inicio (`Home`), **Historial**, **Lo que Nash sabe** (`PerfilConocimiento`), **Sobre Mi**, **Metas**, **Cuerpo**, **Dinero**, placeholder tabs, and **Dev**.
- **Home**: mic (`useAudioRecorder` returns **blob + durationSeconds**), `uploadAudio` sends **`duration_s`**), text chat, `StreamResponse`, and toggleable **Preguntas de hoy** side panel with loading/empty/error states + regenerate button.
- **Cuerpo (V2 for workouts)**: nutrition tracking plus a fuller workout engine UI: discovery modal, exercise profile configuration, plan generation, set logging with RIR/RPE/failure, equipment inventory, measurement protocol + snapshots, PR history, and recent-session history.
- **Dinero (V1)**: Finance discovery modal, monthly summary, category totals, quick expense entry, recent movements list.
- **Goal Discovery (updated)**: right side is now split top/bottom — floating goals graph on top, selected node detail/editor below (save pending goal, set parent, create/delete relations).
- **Historial**: entries with **year in datetime** (`es-MX`), type chip, **`AudioPlayerRow`** (duration from **`duration_s`** or **`loadedmetadata`**).
- **Lo que Nash sabe**: explainer **when each section updates**, **diary highlights**, domain cards, facts, memories; buttons **Actualizar vista** + **Regenerar resúmenes por dominio** → `POST /api/profile/synthesize`.
- **API** (`api.ts`): SSE types include **`diary`**; profile synthesis helpers; **Phase 5 API wrappers/types for discovery, nutrition, exercise, and finance**.

### Data layout

- **DB files**: `~/.nash/nash.db`, `~/.nash/checkpoints.db`, `~/.nash/logs/`, Chroma path `~/.nash/nash_vectors/`.
- **Audio**: **`nash_life_manager/data/audio/*.webm`** (gitignored via `data/audio/.gitignore`); DB stores paths like **`data/audio/<filename>`**.

### Dependencies / runtime

**Full matrix:** see **`ENVIRONMENT.md`** (OpenAI/Ollama provider settings, FFmpeg, Python/Node versions, ports, ASR runtime notes, run commands).

In short: **Python 3.11+** + `pip install -r requirements.txt`, **Node 20+** + `npm install` in `frontend/`, **`NASH_OPENAI_API_KEY`** exported for the default reasoning path, **local Chroma embeddings** (auto-download on first use), **FFmpeg** recommended for Parakeet ASR, and optional `HF_TOKEN` if the ASR repo is gated, **uvicorn on port 8002** to match Vite proxy.

---

## Key takeaways from the conversation (decisions & gotchas)

1. **Obsidian removed** — profile lives in SQLite + future Chroma, not a vault.
2. **LangGraph over Deep Agents** — deterministic tools, local SQL, no alpha harness / cloud tracing dependency.
3. **Multi-topic entries** — handled via **SemanticDecomposer** + **`semantic_units`** retrieval; a single transcript is still stored as one diary row, but its sub-patterns now also get extracted into typed semantic units.
4. **“Lo que Nash sabe” was empty** because domain **`profile_summaries`** were only filled by **manual `/api/profile/synthesize`** (or future background job), not by every chat. **Diary highlights** were added so the tab always reflects **saved voice/text diary rows**.
5. **Duplicate diary rows**: voice path **always** inserts diary first; agent is instructed **not** to `log_diary_entry` again for that turn; migration **links** audio to existing row if same transcript and no `audio_path`.
6. **Dev panel** is a **tab**, not a global shortcut (Chrome bookmark conflict).
7. **Phase order**: Goals/Calendar/Time = **Phase 4**; Body = 5; Money = 6 (per user).
8. **Language**: UI Spanish; dev comments English; Parakeet ASR supports mixed Spanish-English speech.
9. **LLM dependency changed on July 25, 2026**: if `NASH_OPENAI_API_KEY` is present, chat/summary/discovery/question flows use OpenAI; if it is missing, those flows fail on provider init. Ollama is now optional unless you explicitly switch back to it.
10. **Daily questions bug fixed (2026-04-02)**: parser now normalizes model outputs like `tipo: memory_archaeology (MI)`; previously this caused `questions_generated: 0`.
11. **Question generation latency**: `Generar ahora` is a full LLM call and commonly takes ~20–40 seconds on current setup.
12. **Goals graph V1 (2026-04-06)**: goals now support hierarchy (`parent_goal_id`) and explicit graph relations (`supports`, `depends_on`, etc.) with visual editing in discovery mode.
13. **Finance advisory reset (July 25, 2026)**: the user wants Nash to behave more like a debt/financial advisor grounded in both spending data and emotional/self-sabotage patterns. The immediate next step is statement-PDF ingestion plus debt-vs-loan comparison logic, not just manual expense tracking.
14. **Workout philosophy reset (August 27, 2026)**: the user explicitly wants muscle gain without fantasy-planning or shame loops. The engine should guarantee a bare-minimum useful workout, adapt to home vs gym reality, log failure without over-prescribing it, and coordinate with emotional/nutrition patterns from daily entries.

---

## Recent messages / context (condensed)

- User wanted **accessible audio** → **`data/audio` in repo**, legacy copy, historial + processing + short summary.
- User wanted **“everything Nash thinks”** tab → expanded profile endpoint + UI; clarified **update cadence** + **Regenerar resúmenes**.
- **Historial**: show **year** and **audio duration** clearly → locale string + `AudioPlayerRow`.
- User asked to **continue Phase 2** → `semantic_decomposer.py` moved from stub to active extraction/storage path.
- Plans copied into repo: **`nash_life_manager_plan.md`** + **`nash_life_manager_plan_reference.md`**.
- Home keeps top tab navigation; discovery questions are shown in a toggleable right panel.
- Investigated production issue where **Generar ahora** appeared stuck: request returned after ~30s with empty list because parser rejected `tipo` values with framework suffixes. Fixed in `backend/agent/question_engine.py`.
- Re-triggered last diary brief summary and profile domain synthesis successfully after Ollama recovery.
- Implemented Phase 5 V1 UI + API integration for **Cuerpo** and **Dinero** (discovery + tracking flows).
- Migrated the reasoning layer toward OpenAI with a privacy boundary:
  - shared `backend/llm.py` provider gateway,
  - outbound pseudonymization (default alias: `Antonio`),
  - local-name restoration for UI/storage,
  - local Chroma embedding fallback so semantic retrieval no longer requires Ollama.
- Built **Workout Engine V2** on **August 27, 2026**:
  - expanded body schema and API for equipment, measurements, richer session logs, and PRs,
  - added deterministic primary/fallback training plans,
  - injected workout state into Nash's profile context,
  - updated exercise discovery to collect barriers, enjoyment, preferred days/location, and minimum vs optimal training windows.

---

## Next steps (recommended order)

Aligned with **`nash_life_manager_plan.md`** / **`nash_life_manager_plan_reference.md`**:

1. **Phase 6 iteration (Finance):** statement PDF ingestion, debt strategy cards (avalanche/snowball), envelope budgeting, recurring payment tracking, and loan-vs-card payoff comparison.
2. **Phase 5 follow-through (Body):** nutrition audio logging UX, macro estimation pipeline, calendar coordination, and deeper adaptation between diary-based patterns, readiness, and workout planning.
3. **QuestionEngine UX/perf:** improve long-running generation feedback/retry flow and reduce perceived wait.
4. **Phase 8 Work module:** projects, tasks, sessions, distractions, tools + Work tab.
5. **Meta layer:** session cards, “why this question”, what Nash knows/needs.
6. Later: dashboard polish, Tauri wrapper, advanced advisory features.

**Immediate practical checklist for a new session**

- [ ] Confirm `NASH_OPENAI_API_KEY` is exported (or intentionally switch `NASH_LLM_PROVIDER=ollama`).
- [ ] `uvicorn backend.main:app --reload --port 8002` from repo root (with venv).
- [ ] `npm run dev` in `frontend/`; open Historial + Lo que Nash sabe after a voice test.
- [ ] Expect the first semantic retrieval call to download the local Chroma ONNX embedding model once.
- [ ] Read **`nash_life_manager_plan.md`** then skim **`nash_life_manager_plan_reference.md`** for tables and research-backed features.

---

## Quick file map

```
nash_life_manager/
├── CONTEXT_HANDOFF.md          ← this file
├── nash_life_manager_plan.md   ← living roadmap
├── nash_life_manager_plan_reference.md  ← full original plan text
├── backend/main.py
├── backend/config.py
├── backend/db/schema.py
├── backend/agent/graph.py
├── backend/agent/prompts.py
├── backend/agent/profile_synthesize.py
├── backend/agent/semantic_decomposer.py  # active semantic unit extraction
├── backend/audio/transcriber.py
├── backend/audio/brief_summary.py
├── backend/audio/ingest.py
├── data/audio/                 # recordings (gitignored blobs)
└── frontend/src/
    ├── App.tsx
    ├── api.ts
    ├── components/tabs/Home.tsx
    ├── components/tabs/Historial.tsx
    ├── components/tabs/PerfilConocimiento.tsx
    └── components/AudioPlayerRow.tsx
```

---

*Generated for continuity across tools/environments. Update this file when major milestones land (e.g. SemanticDecomposer wired, Work module shipped).*
