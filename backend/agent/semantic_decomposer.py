"""
Phase 2 — SemanticDecomposer.

Extracts typed semantic units from a single transcript (memory, diary_feeling,
pattern_connection, etc.), stores in `semantic_units` table + Chroma.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from typing import Any

import structlog
from langchain_core.messages import HumanMessage

from backend.config import PROFILE_DOMAINS
from backend.db.schema import (
    get_self_profile,
    insert_semantic_unit,
    insert_structured_memory,
    update_semantic_unit_chroma_id,
)
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
    "action_item",
]

VALID_LIFE_PERIODS = ["childhood", "adolescence", "youth", "present", "unspecified"]
VALID_VALENCES = ["positive", "negative", "conflicted", "neutral"]
VALID_POTENTIALS = ["low", "medium", "high"]

# Regex patterns
_UNIT_DELIMITER = re.compile(r"---UNIDAD---", re.IGNORECASE)
_FIELD_PATTERN = re.compile(
    r"^\*{0,2}(tipo|contenido|periodo|edad|edad_fin|anio|anio_fin|temas|valencia|dominios|potencial|titulo|lugar|personas|detalle_sensorial|tipo_recuerdo|importancia|accion_titulo|fecha|hora|duracion|recurrencia|prioridad|flexibilidad|confianza)\*{0,2}\s*:\s*(.*)$",
    re.IGNORECASE | re.MULTILINE,
)

DECOMPOSE_PROMPT = """Eres un analizador semantico para un diario personal en espanol.

Fecha local actual: {today}

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
- action_item: tarea, cita o actividad futura concreta que la persona realmente debe hacer. No uses este tipo para deseos vagos.

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
titulo: [titulo corto; especialmente para memory o action_item]
lugar: [lugar mencionado, o vacio]
personas: [personas involucradas, separadas por comas, o vacio]
detalle_sensorial: [imagen, sonido, olor o detalle vivido del recuerdo, o vacio]
tipo_recuerdo: [evento, etapa, persona, lugar, logro, perdida, cotidiano u otro; o vacio]
importancia: [1-5 si puede inferirse razonablemente, o vacio]
edad_fin: [fin de rango de edad si se menciona, o vacio]
anio: [ano explicito de inicio si se menciona, o vacio]
anio_fin: [ano explicito de fin si se menciona, o vacio]
accion_titulo: [para action_item, verbo + resultado concreto; o vacio]
fecha: [para action_item, YYYY-MM-DD solo si se puede resolver; o vacio]
hora: [para action_item, HH:MM solo si se menciona; o vacio]
duracion: [minutos estimados para action_item; o vacio]
recurrencia: [texto de recurrencia como "3 veces por semana"; o vacio]
prioridad: [1-5 para action_item, o vacio]
flexibilidad: [fixed, movable o free para action_item; o vacio]
confianza: [0.0-1.0 sobre los metadatos temporales extraidos]

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

    prompt = DECOMPOSE_PROMPT.format(transcript=text, today=date.today().isoformat())

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
                metadata_json=json.dumps(unit.get("metadata", {}), ensure_ascii=False),
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
            _materialize_structured_unit(unit, unit_id, diary_entry_id)
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
                ages = [int(number) for number in re.findall(r"\d{1,3}", value)]
                if ages:
                    unit["age_referenced"] = ages[0]
                    unit.setdefault("metadata", {})["age_start"] = ages[0]
                    if len(ages) > 1:
                        unit["metadata"]["age_end"] = ages[1]
            elif field == "edad_fin":
                number = _first_int(value)
                if number is not None:
                    unit.setdefault("metadata", {})["age_end"] = number
            elif field == "anio":
                number = _first_int(value)
                if number and 1900 <= number <= datetime.now().year + 1:
                    unit.setdefault("metadata", {})["occurred_year_start"] = number
            elif field == "anio_fin":
                number = _first_int(value)
                if number and 1900 <= number <= datetime.now().year + 1:
                    unit.setdefault("metadata", {})["occurred_year_end"] = number
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
            elif field in {"titulo", "lugar", "detalle_sensorial", "tipo_recuerdo", "accion_titulo", "fecha", "hora", "recurrencia", "flexibilidad"}:
                if value:
                    key_map = {
                        "titulo": "title",
                        "lugar": "place_name",
                        "detalle_sensorial": "sensory_details",
                        "tipo_recuerdo": "memory_type",
                        "accion_titulo": "action_title",
                        "fecha": "date",
                        "hora": "time",
                        "recurrencia": "recurrence_text",
                        "flexibilidad": "flexibility",
                    }
                    unit.setdefault("metadata", {})[key_map[field]] = value
            elif field == "personas":
                unit.setdefault("metadata", {})["people"] = [
                    person.strip() for person in value.split(",") if person.strip()
                ]
            elif field in {"importancia", "duracion", "prioridad"}:
                number = _first_int(value)
                if number is not None:
                    key_map = {
                        "importancia": "significance",
                        "duracion": "duration_min",
                        "prioridad": "priority",
                    }
                    unit.setdefault("metadata", {})[key_map[field]] = number
            elif field == "confianza":
                try:
                    unit.setdefault("metadata", {})["confidence"] = max(0.0, min(1.0, float(value)))
                except ValueError:
                    pass

        # Validate required fields
        if unit.get("type") and unit.get("content"):
            units.append(unit)

    return units


def _first_int(value: str) -> int | None:
    match = re.search(r"\d+", value or "")
    return int(match.group(0)) if match else None


def _years_from_ages(metadata: dict) -> tuple[int | None, int | None]:
    explicit_start = metadata.get("occurred_year_start")
    explicit_end = metadata.get("occurred_year_end")
    if explicit_start:
        return int(explicit_start), int(explicit_end or explicit_start)
    profile = get_self_profile() or {}
    birth_date = profile.get("birth_date")
    if not birth_date or metadata.get("age_start") is None:
        return None, None
    try:
        birth_year = date.fromisoformat(birth_date).year
    except ValueError:
        return None, None
    age_start = int(metadata["age_start"])
    age_end = int(metadata.get("age_end", age_start))
    # An age spans two calendar years unless the exact event date is known.
    return birth_year + age_start, birth_year + age_end + 1


def _materialize_structured_unit(
    unit: dict[str, Any],
    unit_id: int,
    diary_entry_id: int | None,
) -> None:
    metadata = dict(unit.get("metadata") or {})
    if unit["type"] == "memory":
        year_start, year_end = _years_from_ages(metadata)
        insert_structured_memory(
            {
                "semantic_unit_id": unit_id,
                "diary_entry_id": diary_entry_id,
                "title": metadata.get("title") or unit["content"][:100],
                "raw_transcript": unit["content"],
                "life_period": unit.get("life_period") or "unspecified",
                "occurred_year_start": year_start,
                "occurred_year_end": year_end,
                "age_start": metadata.get("age_start") or unit.get("age_referenced"),
                "age_end": metadata.get("age_end") or metadata.get("age_start") or unit.get("age_referenced"),
                "place_name": metadata.get("place_name"),
                "people": metadata.get("people") or [],
                "themes": unit.get("topics") or [],
                "emotional_valence": unit.get("emotional_valence"),
                "memory_type": metadata.get("memory_type"),
                "significance": metadata.get("significance"),
                "sensory_details": metadata.get("sensory_details"),
                "confidence": metadata.get("confidence"),
            }
        )
    elif unit["type"] == "action_item":
        from backend.calendar_engine import create_diary_action_suggestion, parse_cadence_text

        recurrence_text = metadata.get("recurrence_text")
        if recurrence_text:
            metadata["recurrence"] = parse_cadence_text(recurrence_text)
        create_diary_action_suggestion(
            semantic_unit_id=unit_id,
            diary_entry_id=diary_entry_id,
            content=unit["content"],
            metadata=metadata,
        )
