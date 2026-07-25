# Nash — environment, dependencies, and runtime

Use this when cloning the repo or running in a new machine (e.g. Claude Code in terminal).

---

## Platforms

| Component | Notes |
|-----------|--------|
| **Target** | **macOS on Apple Silicon (M1/M2/M3/M4)** — matches the original plan (16GB RAM, local-first runtime). |
| **Python backend** | Uses NVIDIA Parakeet ASR. Default points to local model path `~/.nash/models/parakeet-tdt-0.6b-v3` via **NeMo** backend (with fallback support for Transformers-compatible ASR models). |
| **Frontend** | Any OS with **Node 20+** (or current LTS). |

---

## System prerequisites

1. **OpenAI API key** — required for the default reasoning path.
   - Put it in your shell profile or export it before running:
     ```bash
     export NASH_OPENAI_API_KEY="sk-..."
     ```
   - **Default model path in code:** `NASH_LLM_PROVIDER=openai`, `NASH_OPENAI_MODEL=gpt-5.6`
   - **Privacy mode:** `NASH_REMOTE_PRIVACY_MODE=anonymized` (default) pseudonymizes outbound prompts; `NASH_REMOTE_ALIAS_NAME=Antonio` is the default alias used for the user's own name.

2. **Ollama** — optional fallback now, not required for the default setup.
   - Use it only if you intentionally set `NASH_LLM_PROVIDER=ollama`.
   - Example fallback model:
     ```bash
     ollama pull drivedenpadev/deepseek-v3.2
     ```

3. **FFmpeg** — **Strongly recommended.** Transformers ASR audio loading often uses ffmpeg under the hood; missing ffmpeg can cause transcription errors (e.g. “Error opening input”).  
   - macOS (Homebrew): `brew install ffmpeg`

4. **Modern browser** — for the UI: **Chrome or Safari** with **microphone** permission for `localhost`.

5. **Disk / network** — If local model path `~/.nash/models/parakeet-tdt-0.6b-v3` is missing, download it once from Hugging Face (see `ASR_MODEL` in `backend/config.py`).
   - If the repo is gated, export a token before running:
     ```bash
     export HF_TOKEN=hf_xxx
     ```
   - First-time semantic retrieval also downloads Chroma's default local ONNX embedding model (`all-MiniLM-L6-v2`) into `~/.cache/chroma/`.

---

## Python

- **Version:** **3.11+** (3.13 used in one dev venv; stick to 3.11–3.13 per your comfort).
- **Virtualenv** at repo root is typical: `.venv`

```bash
cd /path/to/nash_life_manager
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

- **`requirements.txt`** lists FastAPI, LangGraph, **`langchain-openai` + `openai`**, optional `langchain-ollama`, ChromaDB, aiosqlite, and ASR stack deps (`torch`, `transformers`, `nemo_toolkit`, plus NeMo runtime companion deps).  
- **`pydub`** may expect **ffmpeg** for some formats.

---

## Node.js (frontend)

- **Node:** **20+** (LTS recommended).
- **Install:**

```bash
cd frontend
npm install
npm run dev      # Vite dev server (default http://localhost:5173)
```

- **Proxy:** `vite.config.ts` proxies **`/api`** and **`/media`** to **`http://localhost:8002`** — the backend must listen on **8002** (or change both sides).

---

## How to run (typical dev)

**Terminal 1 — API**

```bash
cd /path/to/nash_life_manager
source .venv/bin/activate
uvicorn backend.main:app --reload --port 8002
```

**Terminal 2 — UI**

```bash
cd /path/to/nash_life_manager/frontend
npm run dev
```

**Checks**

- `GET http://127.0.0.1:8002/api/health` → `{"status":"ok",...}`
- Open `http://localhost:5173` and use Inicio / Historial / Lo que Nash sabe.

**LLM sanity checks (Jul 25, 2026)**

- `python - <<'PY' ... get_chat_model(...) ... PY` can be used to smoke-test the OpenAI path when `NASH_OPENAI_API_KEY` is exported.
- `POST /api/questions/generate` can still take noticeable time because reasoning models think before responding.
- If it returns empty (`{"ok": true, "questions": []}`), inspect `~/.nash/logs/nash.log` for `question_engine_llm_error` or `questions_generated` counts.

---

## Configuration (code)

| Setting | Location | Meaning |
|---------|----------|---------|
| LLM provider | `backend/config.py` → `LLM_PROVIDER` | Default `openai`; set to `ollama` for local fallback |
| OpenAI API key | `NASH_OPENAI_API_KEY` | Local env var read by the backend |
| OpenAI model | `OPENAI_MODEL` | Default `gpt-5.6` |
| OpenAI privacy mode | `REMOTE_PRIVACY_MODE` | Default `anonymized` |
| Remote alias name | `REMOTE_ALIAS_NAME` | Default `Antonio` for outbound pseudonymization |
| Embedding provider | `EMBEDDING_PROVIDER` | Default `local` (Chroma ONNX MiniLM) |
| Ollama chat model | `OLLAMA_MODEL` | Optional local fallback |
| Ollama embed model | `OLLAMA_EMBED_MODEL` | Optional when `EMBEDDING_PROVIDER=ollama` |
| ASR model id/path | `ASR_MODEL` | Defaults to `~/.nash/models/parakeet-tdt-0.6b-v3`; can be overridden with env var `ASR_MODEL` (HF id or local path) |
| ASR runtime backend | `ASR_BACKEND` | `auto` (default), `nemo`, or `transformers` |
| ASR auth token (optional) | `ASR_HF_TOKEN` | Read from `HF_TOKEN` or `HUGGINGFACE_HUB_TOKEN` for gated HF repos |
| ASR chunk length | `ASR_CHUNK_LENGTH_S` | Default `120`; NeMo/Parakeet long-audio chunks are 2 minutes |
| ASR word rewind | `ASR_REWIND_WORDS` | Default `15`; next NeMo chunk starts at the timestamp of word `-15` from the previous chunk when timestamps are available |
| App DB | `~/.nash/nash.db` | Diary, profile, memories, … |
| LangGraph checkpoints | `~/.nash/checkpoints.db` | Conversation state |
| Audio files | `REPO_ROOT/data/audio/` | Recordings (gitignored blobs) |
| Chroma | `~/.nash/nash_vectors/` | Vector store path |
| Logs | `~/.nash/logs/nash.log` | structlog JSON (if configured) |

---

## CORS / ports

- FastAPI allows origins including **`http://localhost:5173`** and **`5174`** (`backend/main.py`). Add your port if Vite uses another.

---

## Optional: Hugging Face cache

- Parakeet model weights cache under the usual **HF cache** (`~/.cache/huggingface` or `HF_HOME`). Offline use after first download.

---

## Related docs

- **`CONTEXT_HANDOFF.md`** — product summary, architecture, next steps.
- **`nash_life_manager_plan.md`** — living roadmap.
- **`nash_life_manager_plan_reference.md`** — long-form plan + research notes.

---

## Troubleshooting Notes (Jul 25, 2026)

- If the OpenAI key is missing, the chat/summary/discovery/question features fail at runtime with a provider init error.
- The first semantic-retrieval call with `EMBEDDING_PROVIDER=local` downloads the local ONNX model once (~79MB) before queries become fast.
- If you intentionally switch back to Ollama and it is down, chat/summary/discovery/question calls fail again.
- Fast triage commands:
  - `curl -sS http://127.0.0.1:8002/api/health`
  - `tail -n 80 ~/.nash/logs/nash.log`
