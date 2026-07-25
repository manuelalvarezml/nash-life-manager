"""
QuestionEngine — Daily Discovery Question Generator.

Generates personalized questions using direct, concrete question types
based on research (SFBT scaling, this-or-that preferences, concrete instances).

See docs/question_engine_improved_research.md for full rationale.
"""

from __future__ import annotations

import json
import re
from typing import Any

import structlog
from langchain_core.messages import HumanMessage

from backend.config import (
    PROFILE_DOMAINS,
    QUESTION_TYPES,
    DAILY_QUESTION_COUNT,
    QUESTION_HISTORY_DAYS,
)
from backend.db.schema import (
    get_profile_summaries,
    get_profile_facts,
    get_recent_semantic_units,
    get_questions_in_window,
    get_todays_questions,
    insert_asked_question,
)
from backend.llm import (
    content_to_text,
    get_chat_model,
    restore_local_aliases,
    sanitize_text_for_remote_llm,
)

log = structlog.get_logger()

# All types are direct/concrete - no complex frameworks needed
FRAMEWORK_MAP = {
    "scaling": "SFBT",
    "this_or_that": "preference",
    "last_instance": "concrete",
    "quick_fact": "factual",
    "single_most": "prioritization",
    "tomorrow_change": "action",
}

QUESTION_TYPE_DESCRIPTIONS = {
    "scaling": "Pregunta 1-10 sobre un aspecto de la vida. Rápida, concreta. Ej: 'Del 1 al 10, ¿cómo te sientes con tu trabajo?'",
    "this_or_that": "Elección binaria entre dos opciones. Revela preferencias. Ej: '¿Prefieres más tiempo o más dinero?'",
    "last_instance": "Pregunta sobre una experiencia reciente específica. Ej: '¿Cuándo fue la última vez que te sentiste orgulloso?'",
    "quick_fact": "Dato concreto biográfico o factual. Ej: '¿Cuántos años llevas en tu trabajo actual?'",
    "single_most": "Pregunta de priorización. Ej: '¿Cuál es tu mayor preocupación financiera ahora mismo?'",
    "tomorrow_change": "Cambio inmediato deseado. Ej: '¿Qué cambiarías de tu rutina mañana si pudieras?'",
}


def _normalize_type(value: str) -> str:
    """
    Normalize type strings emitted by the model.
    Examples:
    - "memory_archaeology (MI)"
    - "`future_self`"
    - "exception - SFBT"
    """
    clean = value.strip().lower().strip("*`")
    return re.split(r"[\s(\-]+", clean, maxsplit=1)[0]


def _normalize_domain(value: str) -> str:
    """Normalize domain strings emitted by the model."""
    clean = value.strip().lower().strip("*`")
    return re.split(r"[\s(\-]+", clean, maxsplit=1)[0]

GENERATE_PROMPT = """Eres Nash. Genera preguntas DIRECTAS y CONCRETAS para conocer mejor a la persona usuaria.

IMPORTANTE: Las preguntas deben ser FÁCILES de responder, no vagas ni abstractas.
- Evita preguntas sobre "patrones" o reflexiones abstractas
- Pregunta sobre hechos concretos, preferencias claras, o experiencias recientes específicas
- Cada pregunta debe poder responderse en menos de 30 segundos

CONTEXTO ACTUAL:
{profile_context}

DOMINIOS CON POCA INFORMACIÓN: {gap_domains}

TEMAS RECIENTES: {recent_themes}

PREGUNTAS YA HECHAS (no repetir): {recent_questions}

TIPOS DE PREGUNTAS (usa variedad):

1. **scaling**: Pregunta 1-10 sobre satisfacción, energía, o estado actual
   Ejemplo: "Del 1 al 10, ¿qué tan contento estás con tu balance trabajo-vida?"
   Ejemplo: "¿Qué nota le pondrías a tu nivel de energía hoy?"

2. **this_or_that**: Elección rápida entre DOS opciones (sin "depende")
   Ejemplo: "¿Prefieres tener más tiempo libre o más dinero?"
   Ejemplo: "¿Trabajar solo o en equipo?"
   Ejemplo: "¿Planificar con detalle o improvisar?"

3. **last_instance**: Cuándo fue la ÚLTIMA VEZ que pasó algo específico
   Ejemplo: "¿Cuándo fue la última vez que te sentiste realmente orgulloso de algo?"
   Ejemplo: "¿Qué te hizo reír esta semana?"
   Ejemplo: "¿Cuál fue tu última discusión importante?"

4. **quick_fact**: Dato concreto y directo (número, nombre, fecha)
   Ejemplo: "¿A qué hora te despiertas normalmente?"
   Ejemplo: "¿Cuántas horas trabajas en un día típico?"
   Ejemplo: "¿Tienes mascota? ¿Cuál?"

5. **single_most**: La cosa MÁS importante/grande/principal
   Ejemplo: "¿Cuál es tu mayor fuente de estrés ahora mismo?"
   Ejemplo: "¿Qué relación te gustaría mejorar más?"
   Ejemplo: "¿Cuál es tu mayor fortaleza?"

6. **tomorrow_change**: Cambio concreto para mañana/esta semana
   Ejemplo: "Si pudieras eliminar una tarea de tu rutina, ¿cuál sería?"
   Ejemplo: "¿Qué harías si tuvieras 2 horas extra mañana?"
   Ejemplo: "¿Qué conversación has estado evitando?"

TAREA: Genera exactamente {n} preguntas variadas en español.
- Usa al menos 2 tipos diferentes
- Prioriza dominios con poca información
- Las preguntas deben ser DIRECTAS, CORTAS, y FÁCILES de responder

Formato EXACTO (respétalo para el parsing):
---PREGUNTA---
tipo: [scaling/this_or_that/last_instance/quick_fact/single_most/tomorrow_change]
dominio: [identity/patterns/sabotage/strengths/relationships/narrative/goals]
texto: [la pregunta CORTA y DIRECTA]
porque: [1 frase breve de por qué]
"""


def get_profile_gaps() -> list[str]:
    """Identify domains with thin or missing information."""
    summaries = get_profile_summaries()
    facts = get_profile_facts()

    # Count facts per domain
    facts_per_domain: dict[str, int] = {d: 0 for d in PROFILE_DOMAINS}
    for fact in facts:
        domain = fact.get("domain", "")
        if domain in facts_per_domain:
            facts_per_domain[domain] += 1

    gaps = []
    for domain in PROFILE_DOMAINS:
        summary = summaries.get(domain, "")
        fact_count = facts_per_domain.get(domain, 0)
        # Consider a domain "thin" if summary is short and few facts
        if len(summary) < 100 and fact_count < 3:
            gaps.append(domain)

    return gaps


def calculate_richness_score(transcript: str, unit_count: int) -> float:
    """
    Calculate response richness based on length and semantic density.
    Score ranges from 0.0 to 1.0.
    """
    word_count = len(transcript.split())
    # Base score from word count (100 words = 0.5)
    word_score = min(word_count / 200, 0.5)
    # Bonus from semantic units (each unit adds 0.1, max 0.5)
    unit_score = min(unit_count * 0.1, 0.5)
    return round(word_score + unit_score, 2)


def _parse_questions(raw: str) -> list[dict[str, Any]]:
    """Parse LLM output into question dicts."""
    blocks = re.split(r"---PREGUNTA---", raw, flags=re.IGNORECASE)
    questions = []

    field_pattern = re.compile(
        r"^\*{0,2}(tipo|dominio|texto|porque)\*{0,2}\s*:\s*(.*)$",
        re.IGNORECASE | re.MULTILINE,
    )

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        q: dict[str, Any] = {}
        for line in block.splitlines():
            m = field_pattern.match(line.strip())
            if not m:
                continue
            field = m.group(1).lower()
            value = m.group(2).strip()

            if field == "tipo":
                normalized_type = _normalize_type(value)
                if normalized_type in QUESTION_TYPES:
                    q["type"] = normalized_type
            elif field == "dominio":
                normalized_domain = _normalize_domain(value)
                if normalized_domain in PROFILE_DOMAINS:
                    q["domain"] = normalized_domain
            elif field == "texto" and value:
                q["text"] = value
            elif field == "porque" and value:
                q["why"] = value

        # Validate required fields
        if q.get("type") and q.get("text"):
            q.setdefault("domain", "identity")
            q.setdefault("why", "")
            questions.append(q)

    return questions


def generate_daily_questions(n: int = DAILY_QUESTION_COUNT) -> list[dict]:
    """
    Generate n daily discovery questions.
    Returns list of question dicts with id, text, type, domains, why_asked, was_answered.
    """
    # Check if questions already exist for today
    existing = get_todays_questions()
    if existing:
        log.info("questions_exist", count=len(existing))
        return existing

    # Gather context
    profile_gaps = get_profile_gaps()
    recent_units = get_recent_semantic_units(20)
    recent_questions = get_questions_in_window(QUESTION_HISTORY_DAYS)

    # Build profile context (brief summary of what we know)
    summaries = get_profile_summaries()
    profile_context = "\n".join(
        f"- {domain}: {text[:100]}..." if len(text) > 100 else f"- {domain}: {text}"
        for domain, text in summaries.items()
        if text
    ) or "Sin información de perfil aún."

    # Extract recent themes from semantic units
    recent_themes = set()
    for unit in recent_units[:10]:
        topics = unit.get("topics", "[]")
        if isinstance(topics, str):
            try:
                topics = json.loads(topics)
            except json.JSONDecodeError:
                topics = []
        recent_themes.update(topics)
    recent_themes_str = ", ".join(list(recent_themes)[:10]) or "Sin temas recientes"

    # Format recent questions for non-repeat
    recent_q_text = "\n".join(
        f"- {q['question_text'][:60]}"
        for q in recent_questions[:10]
    ) or "Ninguna"

    # Build prompt (no safety note needed - all types are safe)
    prompt = GENERATE_PROMPT.format(
        profile_context=profile_context,
        gap_domains=", ".join(profile_gaps) or "Ninguno identificado",
        recent_themes=recent_themes_str,
        recent_questions=recent_q_text,
        n=n,
    )

    # Call LLM
    try:
        model = get_chat_model(temperature=0.7, context_window=4096, purpose="analysis")
        response = model.invoke([HumanMessage(content=sanitize_text_for_remote_llm(prompt))])
        raw_output = restore_local_aliases(content_to_text(response.content))
        log.debug("question_engine_raw_output", output=raw_output[:500])
    except Exception as e:
        log.error("question_engine_llm_error", error=str(e))
        return []

    # Parse questions
    questions = _parse_questions(raw_output)

    # Limit to requested count
    questions = questions[:n]

    # Store questions
    stored_questions = []
    for q in questions:
        framework = FRAMEWORK_MAP.get(q["type"], "direct")
        question_id = insert_asked_question(
            question_text=q["text"],
            question_type=q["type"],
            framework=framework,
            domains_targeted=json.dumps([q["domain"]]),
            why_asked=q.get("why"),
        )
        stored_questions.append({
            "id": question_id,
            "question_text": q["text"],
            "question_type": q["type"],
            "domains_targeted": [q["domain"]],
            "framework": framework,
            "why_asked": q.get("why"),
            "was_answered": 0,
        })
        log.info(
            "question_generated",
            question_id=question_id,
            question_type=q["type"],
            domain=q["domain"],
        )

    log.info("questions_generated", count=len(stored_questions))
    return stored_questions
