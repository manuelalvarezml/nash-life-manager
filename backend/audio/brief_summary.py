"""One-line Spanish summary for diary historial (local LLM)."""

import structlog
from langchain_core.messages import HumanMessage

from backend.llm import (
    content_to_text,
    get_chat_model,
    restore_local_aliases,
    sanitize_text_for_remote_llm,
)

log = structlog.get_logger()

_MAX_WORDS = 28


def brief_summary_spanish(transcript: str) -> str:
    text = (transcript or "").strip()
    if not text:
        return ""

    prompt = (
        "Resume en UNA sola frase muy corta en español (máximo "
        f"{_MAX_WORDS} palabras). Solo hechos del texto; no inventes. Texto:\n\n{text}"
    )

    try:
        model = get_chat_model(temperature=0.2, context_window=4096, purpose="summary")
        out = model.invoke([HumanMessage(content=sanitize_text_for_remote_llm(prompt))])
        raw = content_to_text(out.content).replace("\n", " ")
        raw = restore_local_aliases(raw)
        if len(raw) > 220:
            raw = raw[:217] + "…"
        return raw or _fallback_summary(text)
    except Exception as e:
        log.warning("brief_summary_failed", error=str(e))
        return _fallback_summary(text)


def _fallback_summary(text: str) -> str:
    if len(text) <= 140:
        return text
    return text[:137].rsplit(" ", 1)[0] + "…"
