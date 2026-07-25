"""
Phase 2 — SemanticDecomposer.

Extracts typed semantic units from a single transcript (memory, diary_feeling,
pattern_connection, etc.), stores in `semantic_units` table + Chroma.
"""

from __future__ import annotations

import json
import re
from typing import Any

import structlog
from langchain_core.messages import HumanMessage

from backend.config import PROFILE_DOMAINS
from backend.db.schema import insert_semantic_unit, update_semantic_unit_chroma_id
from backend.db.chroma import ingest_semantic_unit
from backend.llm import (
    content_to_text,
    get_chat_model,
    restore_local_aliases,
    sanitize_text_for_remote_llm,
)

log = structlog.get_logger()

VALID_UNIT_TYPES = [
    "memory",
    "pattern_connection",
    "relationship_reflection",
    "diary_feeling",
    "intention",
    "insight",
    "trauma_reference",
    "goal_mention",
    "behavior_observation",
]

VALID_LIFE_PERIODS = ["childhood", "adolescence", "youth", "present", "unspecified"]
VALID_VALENCES = ["positive", "negative", "conflicted", "neutral"]
VALID_POTENTIALS = ["low", "medium", "high"]

# Regex patterns
_UNIT_DELIMITER = re.compile(r"---UNIDAD---", re.IGNORECASE)
_FIELD_PATTERN = re.compile(
    r"^\*{0,2}(tipo|contenido|periodo|edad|temas|valencia|dominios|potencial)\*{0,2}\s*:\s*(.*)$",
    re.IGNORECASE | re.MULTILINE,
)

DECOMPOSE_PROMPT = """Eres un analizador semantico para un diario personal en espanol.

TAREA: Extrae todas las unidades semanticas distintas del siguiente texto. Una entrada puede contener multiples unidades (un recuerdo, una reflexion sobre un patron, un sentimiento actual, etc.).

TIPOS VALIDOS de unidad:
- memory: recuerdo o anecdota del pasado
- pattern_connection: conexion entre eventos o comportamientos repetidos
- relationship_reflection: reflexion sobre relaciones personales
- diary_feeling: sentimiento o estado emocional actual
- intention: intencion o plan futuro
- insight: descubrimiento o realizacion personal
- trauma_reference: referencia a experiencia traumatica o dolorosa
- goal_mention: mencion de meta u objetivo
- behavior_observation: observacion sobre comportamiento propio

PERIODOS DE VIDA: childhood, adolescence, youth, present, unspecified

VALENCIA EMOCIONAL: positive, negative, conflicted, neutral

DOMINIOS: identity, patterns, sabotage, strengths, relationships, narrative, goals

POTENCIAL DE INSIGHT: low (observacion simple), medium (patron o conexion), high (descubrimiento significativo)

Para CADA unidad encontrada, escribe un bloque con este formato exacto:
---UNIDAD---
tipo: [tipo de la lista]
contenido: [el contenido textual de esta unidad, parafraseado brevemente]
periodo: [periodo de vida si aplica, o "unspecified"]
edad: [edad aproximada si se menciona, o dejar vacio]
temas: [lista separada por comas de temas relevantes]
valencia: [valencia emocional]
dominios: [lista separada por comas de dominios que aplican]
potencial: [low/medium/high]

Si NO hay unidades claras que extraer, escribe solamente: SIN_UNIDADES

Texto a analizar:
---
{transcript}
---
"""


def decompose_transcript(
    transcript: str,
    diary_entry_id: int | None = None,
) -> list[dict[str, Any]]:
    """
    Extract semantic units from transcript, store in DB + Chroma.
    Returns list of extracted unit dicts with their IDs.
    """
    text = (transcript or "").strip()
    if not text or len(text) < 20:
        log.info("decomposer_skip", reason="text_too_short", length=len(text))
        return []

    prompt = DECOMPOSE_PROMPT.format(transcript=text)

    try:
        model = get_chat_model(temperature=0.2, context_window=8192, purpose="analysis")
        response = model.invoke([HumanMessage(content=sanitize_text_for_remote_llm(prompt))])
        raw_output = restore_local_aliases(content_to_text(response.content))
    except Exception as e:
        log.error("decomposer_llm_error", error=str(e))
        return []

    if "SIN_UNIDADES" in raw_output.upper():
        log.info("decomposer_no_units", diary_id=diary_entry_id)
        return []

    units = _parse_units(raw_output)
    stored_units = []

    for unit in units:
        try:
            # Insert to SQLite
            unit_id = insert_semantic_unit(
                unit_type=unit["type"],
                content=unit["content"],
                diary_entry_id=diary_entry_id,
                life_period=unit.get("life_period"),
                age_referenced=unit.get("age_referenced"),
                topics=json.dumps(unit.get("topics", [])),
                emotional_valence=unit.get("emotional_valence"),
                domains=json.dumps(unit.get("domains", [])),
                insight_potential=unit.get("insight_potential", "low"),
            )

            # Ingest to Chroma
            metadata = {
                "unit_type": unit["type"],
                "diary_entry_id": diary_entry_id or 0,
                "life_period": unit.get("life_period", "unspecified"),
                "emotional_valence": unit.get("emotional_valence", "neutral"),
                "domains": ",".join(unit.get("domains", [])),
                "insight_potential": unit.get("insight_potential", "low"),
            }
            chroma_id = ingest_semantic_unit(
                unit_id=unit_id,
                content=unit["content"],
                metadata=metadata,
            )

            # Update SQLite with chroma_id
            update_semantic_unit_chroma_id(unit_id, chroma_id)

            unit["id"] = unit_id
            unit["chroma_id"] = chroma_id
            stored_units.append(unit)

            log.info(
                "decomposer_unit_stored",
                unit_id=unit_id,
                unit_type=unit["type"],
                diary_id=diary_entry_id,
            )

        except Exception as e:
            log.error("decomposer_store_error", error=str(e), unit_type=unit.get("type"))

    log.info(
        "decomposer_done",
        units_extracted=len(stored_units),
        diary_id=diary_entry_id,
    )
    return stored_units


def _parse_units(raw: str) -> list[dict[str, Any]]:
    """Parse LLM output into unit dicts."""
    blocks = _UNIT_DELIMITER.split(raw)
    units = []

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        unit: dict[str, Any] = {}
        for line in block.splitlines():
            m = _FIELD_PATTERN.match(line.strip())
            if not m:
                continue
            field = m.group(1).lower()
            value = m.group(2).strip()

            if field == "tipo" and value.lower() in VALID_UNIT_TYPES:
                unit["type"] = value.lower()
            elif field == "contenido" and value:
                unit["content"] = value
            elif field == "periodo":
                lv = value.lower()
                if lv in VALID_LIFE_PERIODS:
                    unit["life_period"] = lv
            elif field == "edad":
                if value:
                    try:
                        unit["age_referenced"] = int(re.sub(r"[^\d]", "", value))
                    except ValueError:
                        pass
            elif field == "temas":
                unit["topics"] = [t.strip() for t in value.split(",") if t.strip()]
            elif field == "valencia":
                lv = value.lower()
                if lv in VALID_VALENCES:
                    unit["emotional_valence"] = lv
            elif field == "dominios":
                doms = [d.strip().lower() for d in value.split(",") if d.strip()]
                unit["domains"] = [d for d in doms if d in PROFILE_DOMAINS]
            elif field == "potencial":
                lv = value.lower()
                if lv in VALID_POTENTIALS:
                    unit["insight_potential"] = lv

        # Validate required fields
        if unit.get("type") and unit.get("content"):
            units.append(unit)

    return units
