from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

import structlog
from langchain_core.messages import BaseMessage
from langchain_ollama import ChatOllama

from backend.config import (
    LLM_MAX_RETRIES,
    LLM_PROVIDER,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OPENAI_API_KEY,
    OPENAI_ANALYSIS_REASONING_EFFORT,
    OPENAI_DISCOVERY_REASONING_EFFORT,
    OPENAI_MODEL,
    OPENAI_REASONING_EFFORT,
    OPENAI_REASONING_MODE,
    OPENAI_SUMMARY_REASONING_EFFORT,
    OPENAI_TIMEOUT_S,
    OPENAI_USE_RESPONSES_API,
    REMOTE_ALIAS_NAME,
    REMOTE_PRIVACY_MODE,
)
from backend.db.schema import get_self_profile

try:
    from langchain_openai import ChatOpenAI
except Exception:
    ChatOpenAI = None

log = structlog.get_logger()

_EMAIL_PATTERN = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
_PHONE_PATTERN = re.compile(r"(?<!\w)(?:\+?\d[\d()\s.-]{7,}\d)(?!\w)")
_URL_PATTERN = re.compile(r"\b(?:https?://|www\.)\S+\b", re.IGNORECASE)
_HANDLE_PATTERN = re.compile(r"(?<!\w)@[A-Za-z0-9_]{2,}")
_LONG_NUMBER_PATTERN = re.compile(r"\b\d{8,}\b")
_MANUEL_PATTERN = re.compile(r"\bmanuel\b", re.IGNORECASE)


def is_openai_provider() -> bool:
    return LLM_PROVIDER == "openai"


def should_redact_identity() -> bool:
    return is_openai_provider() and REMOTE_PRIVACY_MODE == "anonymized"


def get_model_label() -> str:
    return OPENAI_MODEL if is_openai_provider() else OLLAMA_MODEL


def _reasoning_for_purpose(purpose: str) -> dict[str, str]:
    if purpose == "agent":
        return {
            "mode": OPENAI_REASONING_MODE,
            "effort": OPENAI_REASONING_EFFORT,
        }
    if purpose == "discovery":
        return {"effort": OPENAI_DISCOVERY_REASONING_EFFORT}
    if purpose in {"summary", "classification"}:
        return {"effort": OPENAI_SUMMARY_REASONING_EFFORT}
    return {"effort": OPENAI_ANALYSIS_REASONING_EFFORT}


def get_chat_model(
    *,
    temperature: float,
    context_window: int | None = None,
    purpose: str = "analysis",
):
    if is_openai_provider():
        if ChatOpenAI is None:
            raise RuntimeError(
                "langchain-openai is not installed. Run `pip install -r requirements.txt`."
            )
        if not OPENAI_API_KEY:
            raise RuntimeError(
                "NASH_OPENAI_API_KEY (or OPENAI_API_KEY) is not set in the environment."
            )
        return ChatOpenAI(
            model=OPENAI_MODEL,
            api_key=OPENAI_API_KEY,
            temperature=temperature,
            timeout=OPENAI_TIMEOUT_S,
            max_retries=LLM_MAX_RETRIES,
            use_responses_api=OPENAI_USE_RESPONSES_API,
            stream_usage=True,
            reasoning=_reasoning_for_purpose(purpose),
            store=False,
        )

    return ChatOllama(
        model=OLLAMA_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=temperature,
        num_ctx=context_window or 8192,
    )


def _calculate_age(raw_birth_date: str) -> int | None:
    try:
        birth_date = datetime.strptime(raw_birth_date, "%Y-%m-%d").date()
    except ValueError:
        return None

    today = date.today()
    age = today.year - birth_date.year
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        age -= 1
    return age if age >= 0 else None


def build_literal_replacements(profile: dict | None = None) -> list[tuple[str, str]]:
    profile = profile or get_self_profile() or {}
    replacements: list[tuple[str, str]] = []

    preferred_name = (profile.get("preferred_name") or "").strip()
    if preferred_name:
        replacements.append((preferred_name, REMOTE_ALIAS_NAME))

    partner_name = (profile.get("partner_name") or "").strip()
    if partner_name:
        replacements.append((partner_name, "su pareja"))

    current_city = (profile.get("current_city") or "").strip()
    if current_city:
        replacements.append((current_city, "su ciudad actual"))

    current_country = (profile.get("current_country") or "").strip()
    if current_country:
        replacements.append((current_country, "su pais actual"))

    birth_place = (profile.get("birth_place") or "").strip()
    if birth_place:
        replacements.append((birth_place, "su lugar de nacimiento"))

    birth_date = (profile.get("birth_date") or "").strip()
    age = _calculate_age(birth_date) if birth_date else None
    if birth_date and age is not None:
        replacements.append((birth_date, f"{age} anos"))
    elif birth_date:
        replacements.append((birth_date, "su fecha de nacimiento"))

    # Old prompts and summaries may still contain the owner's name literally.
    replacements.append(("Manuel", REMOTE_ALIAS_NAME))
    return sorted(replacements, key=lambda item: len(item[0]), reverse=True)


def sanitize_text_for_remote_llm(
    text: str,
    replacements: list[tuple[str, str]] | None = None,
) -> str:
    if not should_redact_identity():
        return text

    redacted = text
    for literal, replacement in replacements or build_literal_replacements():
        if not literal:
            continue
        redacted = re.sub(re.escape(literal), replacement, redacted, flags=re.IGNORECASE)

    redacted = _MANUEL_PATTERN.sub(REMOTE_ALIAS_NAME, redacted)
    redacted = _EMAIL_PATTERN.sub("[correo]", redacted)
    redacted = _PHONE_PATTERN.sub("[telefono]", redacted)
    redacted = _URL_PATTERN.sub("[url]", redacted)
    redacted = _HANDLE_PATTERN.sub("[usuario_red]", redacted)
    redacted = _LONG_NUMBER_PATTERN.sub("[identificador]", redacted)
    return redacted


def _sanitize_message_content(content: Any) -> Any:
    if isinstance(content, str):
        return sanitize_text_for_remote_llm(content)

    if isinstance(content, list):
        sanitized: list[Any] = []
        for item in content:
            if isinstance(item, str):
                sanitized.append(sanitize_text_for_remote_llm(item))
                continue
            if isinstance(item, dict):
                cloned = dict(item)
                if cloned.get("type") == "text" and isinstance(cloned.get("text"), str):
                    cloned["text"] = sanitize_text_for_remote_llm(cloned["text"])
                sanitized.append(cloned)
                continue
            sanitized.append(item)
        return sanitized

    return content


def content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
                continue
            if isinstance(item, dict):
                if item.get("type") == "text" and isinstance(item.get("text"), str):
                    parts.append(item["text"])
        return "\n".join(part.strip() for part in parts if part and part.strip()).strip()

    return str(content or "").strip()


def restore_local_aliases(text: str) -> str:
    if not text or not should_redact_identity():
        return text

    profile = get_self_profile() or {}
    preferred_name = (profile.get("preferred_name") or "").strip() or "Manuel"

    return re.sub(
        rf"\b{re.escape(REMOTE_ALIAS_NAME)}\b",
        preferred_name,
        text,
        flags=re.IGNORECASE,
    )


def sanitize_messages_for_remote_llm(messages: list[BaseMessage]) -> list[BaseMessage]:
    if not should_redact_identity():
        return messages

    sanitized: list[BaseMessage] = []
    for message in messages:
        if not hasattr(message, "content"):
            sanitized.append(message)
            continue
        sanitized.append(
            message.model_copy(
                update={"content": _sanitize_message_content(message.content)},
                deep=True,
            )
        )
    return sanitized
