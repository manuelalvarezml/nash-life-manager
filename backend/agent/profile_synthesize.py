"""Refresh profile_summaries from recent diary text (local LLM, Spanish)."""

import asyncio
import re
import structlog
from langchain_core.messages import HumanMessage

from backend.config import PROFILE_DOMAINS, SYNTHESIS_ENTRY_INTERVAL
from backend.db.schema import (
    get_recent_diary_entries,
    get_profile_summaries,
    apply_profile_summary_updates,
    get_entry_count,
)
from backend.llm import (
    content_to_text,
    get_chat_model,
    restore_local_aliases,
    sanitize_text_for_remote_llm,
)

log = structlog.get_logger()

# Track last synthesis to avoid redundant runs
_last_synthesis_count: int = 0

_DOMAINS_LINE = re.compile(
    r"^\*{0,2}(identity|patterns|sabotage|strengths|relationships|narrative|goals)\*{0,2}\s*:\s*(.*)$",
    re.IGNORECASE | re.MULTILINE,
)


def _build_diary_blob(entries: list[dict], max_chars: int = 12000) -> str:
    parts: list[str] = []
    total = 0
    for e in entries:
        ts = e.get("timestamp", "")
        t = (e.get("raw_transcript") or "").strip()
        if not t:
            continue
        block = f"[{ts}] {t}\n"
        if total + len(block) > max_chars:
            break
        parts.append(block)
        total += len(block)
    return "\n".join(parts).strip()


def synthesize_profile_from_diaries(max_entries: int = 25) -> dict[str, str]:
    """
    Rewrite domain summaries from recent diary transcripts.
    Returns map domain -> new summary text (may include VACÍO markers stripped).
    """
    entries = get_recent_diary_entries(max_entries)
    blob = _build_diary_blob(entries)
    if not blob:
        log.info("profile_synthesize_skip", reason="no_diary_text")
        return {}

    prev = get_profile_summaries()
    prev_lines = "\n".join(f"- {d}: {(prev.get(d) or '').strip() or '(vacío)'}" for d in PROFILE_DOMAINS)

    prompt = f"""Eres Nash, asistente de vida. La persona usuaria escribe su diario en español (a veces palabras en inglés).

Extractos del diario (más recientes primero):
---
{blob}
---

Resúmenes anteriores por dominio (puedes refinarlos, no inventes hechos no mencionados):
{prev_lines}

TAREA: Para cada dominio escribe un resumen MUY breve en español (1–3 frases), solo basado en los extractos.
Si no hay información en los extractos para un dominio, escribe exactamente: VACÍO

Dominios obligatorios (una línea cada uno, formato exacto "dominio: texto"):
identity:
patterns:
sabotage:
strengths:
relationships:
narrative:
goals:
"""

    model = get_chat_model(temperature=0.25, context_window=8192, purpose="summary")
    out = model.invoke([HumanMessage(content=sanitize_text_for_remote_llm(prompt))])
    raw = restore_local_aliases(content_to_text(out.content))

    updated: dict[str, str] = {}
    for line in raw.splitlines():
        line = line.strip()
        m = _DOMAINS_LINE.match(line)
        if not m:
            continue
        dom = m.group(1).lower()
        text = m.group(2).strip()
        if dom not in PROFILE_DOMAINS:
            continue
        if text.upper().startswith("VACÍO") or text.upper() == "VACIO":
            text = ""
        updated[dom] = text

    log.info("profile_synthesize_parsed", domains=len(updated))
    return updated


def should_trigger_synthesis(current_count: int) -> bool:
    """Check if we should trigger background synthesis based on entry count."""
    global _last_synthesis_count
    if current_count - _last_synthesis_count >= SYNTHESIS_ENTRY_INTERVAL:
        return True
    return False


def mark_synthesis_done():
    """Update the last synthesis count after a successful run."""
    global _last_synthesis_count
    _last_synthesis_count = get_entry_count()


async def run_background_synthesis():
    """Background task for automatic profile synthesis."""
    global _last_synthesis_count
    try:
        log.info("background_synthesis_start")
        updates = await asyncio.to_thread(synthesize_profile_from_diaries, 30)
        if updates:
            await asyncio.to_thread(apply_profile_summary_updates, updates)
            _last_synthesis_count = get_entry_count()
            log.info("background_synthesis_done", domains=list(updates.keys()))
        else:
            log.info("background_synthesis_skip", reason="no_updates")
    except Exception as e:
        log.error("background_synthesis_error", error=str(e))
