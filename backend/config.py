import os
from pathlib import Path


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


REPO_ROOT = Path(__file__).resolve().parent.parent
NASH_HOME = Path.home() / ".nash"
DB_PATH = NASH_HOME / "nash.db"
CHECKPOINT_DB_PATH = NASH_HOME / "checkpoints.db"
# Voice recordings live in the repo under data/audio (easy to open in Finder; gitignored)
AUDIO_DIR = REPO_ROOT / "data" / "audio"
LEGACY_AUDIO_DIR = NASH_HOME / "audio"
VECTOR_DIR = NASH_HOME / "nash_vectors"
LOG_DIR = NASH_HOME / "logs"

# Relative path prefix stored in DB and exposed to the UI (under REPO_ROOT)
AUDIO_DB_PREFIX = "data/audio"

# LLM provider selection.
LLM_PROVIDER = os.getenv("NASH_LLM_PROVIDER", "openai").strip().lower()

# OpenAI reasoning models (default: flagship alias).
OPENAI_API_KEY = os.getenv("NASH_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("NASH_OPENAI_MODEL", "gpt-5.6")
OPENAI_REASONING_MODE = os.getenv("NASH_OPENAI_REASONING_MODE", "standard")
OPENAI_REASONING_EFFORT = os.getenv("NASH_OPENAI_REASONING_EFFORT", "high")
OPENAI_DISCOVERY_REASONING_EFFORT = os.getenv(
    "NASH_OPENAI_DISCOVERY_REASONING_EFFORT",
    "medium",
)
OPENAI_ANALYSIS_REASONING_EFFORT = os.getenv(
    "NASH_OPENAI_ANALYSIS_REASONING_EFFORT",
    "medium",
)
OPENAI_SUMMARY_REASONING_EFFORT = os.getenv(
    "NASH_OPENAI_SUMMARY_REASONING_EFFORT",
    "low",
)
OPENAI_TIMEOUT_S = float(os.getenv("NASH_OPENAI_TIMEOUT_S", "120"))
OPENAI_USE_RESPONSES_API = _env_flag("NASH_OPENAI_USE_RESPONSES_API", True)
LLM_MAX_RETRIES = int(os.getenv("NASH_LLM_MAX_RETRIES", "2"))
REMOTE_PRIVACY_MODE = os.getenv("NASH_REMOTE_PRIVACY_MODE", "anonymized").strip().lower()
REMOTE_ALIAS_NAME = os.getenv("NASH_REMOTE_ALIAS_NAME", "Antonio").strip() or "Antonio"

# Optional Ollama fallback and local embedding path.
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("NASH_OLLAMA_MODEL", "drivedenpadev/deepseek-v3.2")
OLLAMA_SYNTH_MODEL = os.getenv("NASH_OLLAMA_SYNTH_MODEL", OLLAMA_MODEL)
OLLAMA_EMBED_MODEL = os.getenv("NASH_OLLAMA_EMBED_MODEL", "nomic-embed-text")
EMBEDDING_PROVIDER = os.getenv("NASH_EMBEDDING_PROVIDER", "local").strip().lower()

# Speech-to-text model (Hugging Face via Transformers).
# Spanish-focused model with support for mixed Spanish/English speech.
ASR_MODEL = os.getenv(
    "ASR_MODEL",
    str(Path.home() / ".nash" / "models" / "parakeet-tdt-0.6b-v3"),
)
# Backend selection for ASR runtime: auto | transformers | nemo
ASR_BACKEND = os.getenv("ASR_BACKEND", "auto")
# Optional token for gated/private Hugging Face repos.
ASR_HF_TOKEN = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_HUB_TOKEN")
# Chunking keeps long audios stable and memory-safe.
ASR_CHUNK_LENGTH_S = int(os.getenv("ASR_CHUNK_LENGTH_S", "120"))
ASR_STRIDE_LENGTH_S = int(os.getenv("ASR_STRIDE_LENGTH_S", "5"))
# For NeMo/Parakeet chunking, rewind to the timestamp of this many words before
# the end of the previous chunk. This replaces a fixed seconds-based overlap.
ASR_REWIND_WORDS = int(os.getenv("ASR_REWIND_WORDS", "15"))

# Profile synthesis triggers after every N diary entries
SYNTHESIS_ENTRY_INTERVAL = 5

PROFILE_DOMAINS = [
    "identity",
    "patterns",
    "sabotage",
    "strengths",
    "relationships",
    "narrative",
    "goals",
]

# Question Engine configuration (improved based on research)
# See docs/question_engine_improved_research.md for rationale
QUESTION_TYPES = [
    "scaling",           # 1-10 rating (SFBT) - quick, concrete
    "this_or_that",      # Binary choice - reveals preferences
    "last_instance",     # Recent specific experience
    "quick_fact",        # Direct biographical/factual
    "single_most",       # Prioritization question
    "tomorrow_change",   # Immediate desires/changes
]
DAILY_QUESTION_COUNT = 5
QUESTION_HISTORY_DAYS = 30
# All new types are emotionally safe - no need for safety filter
UNSAFE_QUESTION_TYPES: list[str] = []


def ensure_dirs():
    for d in [NASH_HOME, AUDIO_DIR, VECTOR_DIR, LOG_DIR, LEGACY_AUDIO_DIR]:
        d.mkdir(parents=True, exist_ok=True)
