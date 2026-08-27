from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import structlog
from langchain_core.messages import HumanMessage

from backend.db.calendar import (
    find_calendar_item_candidates,
    finish_schedule_input,
    get_active_calendar_series,
    get_calendar_item,
    get_calendar_items,
    get_calendar_suggestion,
    get_calendar_suggestions,
    get_schedule_preferences,
    get_unscheduled_items,
    insert_calendar_item,
    insert_calendar_series,
    insert_calendar_suggestion,
    insert_schedule_input,
    resolve_calendar_suggestion,
    update_calendar_item,
    update_calendar_series,
)
from backend.db.schema import get_exercise_profile, get_finance_profile, get_goals
from backend.llm import (
    content_to_text,
    get_chat_model,
    restore_local_aliases,
    sanitize_text_for_remote_llm,
)

log = structlog.get_logger()

VALID_COMMANDS = {
    "create",
    "reschedule",
    "cancel",
    "complete",
    "rearrange",
    "update_series",
    "unknown",
}
DAY_NAMES = {
    "lunes": 0,
    "monday": 0,
    "martes": 1,
    "tuesday": 1,
    "miercoles": 2,
    "miércoles": 2,
    "wednesday": 2,
    "jueves": 3,
    "thursday": 3,
    "viernes": 4,
    "friday": 4,
    "sabado": 5,
    "sábado": 5,
    "saturday": 5,
    "domingo": 6,
    "sunday": 6,
}

CALENDAR_INPUT_PROMPT = """Eres el interprete de agenda de Nash. Convierte una instruccion en espanol en UN objeto JSON.

Fecha y hora local: {now_local}
Zona horaria: {timezone}

Comandos validos:
- create: crear una tarea, evento, bloque o rutina.
- reschedule: mover una actividad concreta.
- cancel: cancelar una actividad concreta.
- complete: marcar una actividad concreta como hecha.
- rearrange: reorganizar un dia, rango, categoria o conjunto completo.
- update_series: cambiar una actividad recurrente completa.
- unknown: no hay suficiente informacion.

Devuelve SOLO JSON valido con estas claves. Usa null si no se sabe:
{{
  "command_type": "create|reschedule|cancel|complete|rearrange|update_series|unknown",
  "title": "titulo corto de la actividad",
  "target_query": "texto corto para encontrar la actividad existente",
  "description": "detalle util",
  "item_type": "event|task|focus|routine|reminder",
  "date": "YYYY-MM-DD",
  "time": "HH:MM",
  "end_time": "HH:MM",
  "due_date": "YYYY-MM-DD",
  "duration_min": 30,
  "recurrence": {{"frequency":"daily|weekly|monthly", "interval":1, "days_of_week":[0], "times_per_week":null, "day_of_month":null, "until":null}},
  "scope": {{"start_date":"YYYY-MM-DD", "end_date":"YYYY-MM-DD", "source_kind":null}},
  "priority": 3,
  "flexibility": "fixed|movable|free",
  "energy_required": 3,
  "location": null,
  "confidence": 0.0
}}

Reglas:
- Convierte fechas relativas usando la fecha local indicada.
- Una cita con otra persona o una hora inamovible es fixed. Una tarea personal suele ser movable.
- Si dice todos los dias, X veces por semana, cada mes o dias especificos, completa recurrence.
- Para "reorganiza hoy/esta semana", usa rearrange y completa scope.
- No inventes una hora si no se dijo; dejala null para que el planificador busque espacio.
- No conviertas deseos vagos en compromisos; usa unknown si no hay una accion concreta.

Instruccion:
{text}
"""


def _now_local() -> datetime:
    prefs = get_schedule_preferences()
    try:
        zone = ZoneInfo(prefs.get("timezone") or "America/Lima")
    except Exception:
        zone = ZoneInfo("America/Lima")
    return datetime.now(zone).replace(tzinfo=None)


def _parse_json_object(raw: str) -> dict:
    candidate = raw.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?\s*", "", candidate, flags=re.IGNORECASE)
        candidate = re.sub(r"\s*```$", "", candidate)
    try:
        parsed = json.loads(candidate)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", candidate, flags=re.DOTALL)
        if not match:
            return {}
        try:
            parsed = json.loads(match.group(0))
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}


def _clean_iso_date(value: Any) -> str | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10]).isoformat()
    except ValueError:
        return None


def _clean_time(value: Any) -> str | None:
    if not value:
        return None
    match = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", str(value))
    if not match:
        return None
    return f"{int(match.group(1)):02d}:{match.group(2)}"


def _clamp_int(value: Any, low: int, high: int, fallback: int | None = None) -> int | None:
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return fallback


def _normalize_recurrence(raw: Any) -> dict | None:
    if not isinstance(raw, dict):
        return None
    frequency = str(raw.get("frequency") or "").lower()
    if frequency not in {"daily", "weekly", "monthly"}:
        return None
    days = []
    for value in raw.get("days_of_week") or []:
        day = _clamp_int(value, 0, 6)
        if day is not None and day not in days:
            days.append(day)
    return {
        "frequency": frequency,
        "interval": _clamp_int(raw.get("interval"), 1, 12, 1),
        "days_of_week": sorted(days),
        "times_per_week": _clamp_int(raw.get("times_per_week"), 1, 7),
        "day_of_month": _clamp_int(raw.get("day_of_month"), 1, 31),
        "until": _clean_iso_date(raw.get("until")),
    }


def _normalize_interpretation(raw: dict, original_text: str) -> dict:
    command = str(raw.get("command_type") or "unknown").lower()
    if command not in VALID_COMMANDS:
        command = "unknown"
    scope = raw.get("scope") if isinstance(raw.get("scope"), dict) else {}
    normalized = {
        "command_type": command,
        "title": str(raw.get("title") or "").strip() or None,
        "target_query": str(raw.get("target_query") or "").strip() or None,
        "description": str(raw.get("description") or "").strip() or None,
        "item_type": str(raw.get("item_type") or "task").lower(),
        "date": _clean_iso_date(raw.get("date")),
        "time": _clean_time(raw.get("time")),
        "end_time": _clean_time(raw.get("end_time")),
        "due_date": _clean_iso_date(raw.get("due_date")),
        "duration_min": _clamp_int(raw.get("duration_min"), 5, 720),
        "recurrence": _normalize_recurrence(raw.get("recurrence")),
        "scope": {
            "start_date": _clean_iso_date(scope.get("start_date")),
            "end_date": _clean_iso_date(scope.get("end_date")),
            "source_kind": str(scope.get("source_kind") or "").strip() or None,
        },
        "priority": _clamp_int(raw.get("priority"), 1, 5, 3),
        "flexibility": str(raw.get("flexibility") or "movable").lower(),
        "energy_required": _clamp_int(raw.get("energy_required"), 1, 5),
        "location": str(raw.get("location") or "").strip() or None,
        "confidence": max(0.0, min(1.0, float(raw.get("confidence") or 0.0))),
        "original_text": original_text,
    }
    if normalized["item_type"] not in {"event", "task", "focus", "routine", "reminder"}:
        normalized["item_type"] = "task"
    if normalized["flexibility"] not in {"fixed", "movable", "free"}:
        normalized["flexibility"] = "movable"
    return normalized


def _fallback_interpretation(text: str) -> dict:
    lowered = text.lower()
    now = _now_local()
    command = "create"
    if any(word in lowered for word in ["cancela", "elimina", "borra"]):
        command = "cancel"
    elif any(word in lowered for word in ["complet", "ya hice", "terminé", "termine"]):
        command = "complete"
    elif any(word in lowered for word in ["reorganiza", "reordena", "reacomoda"]):
        command = "rearrange"
    elif any(word in lowered for word in ["mueve", "cambia de hora", "reprograma"]):
        command = "reschedule"
    target_date = now.date()
    if "mañana" in lowered or "manana" in lowered:
        target_date += timedelta(days=1)
    elif "pasado mañana" in lowered or "pasado manana" in lowered:
        target_date += timedelta(days=2)
    time_match = re.search(r"(?:a las|desde las|las)\s+(\d{1,2})(?::(\d{2}))?", lowered)
    parsed_time = None
    if time_match:
        parsed_time = f"{int(time_match.group(1)) % 24:02d}:{time_match.group(2) or '00'}"
    recurrence = parse_cadence_text(text)
    title = re.sub(
        r"^(?:tengo que|debo|necesito|agenda|agendar|programa|programar|recuerdame|recuérdame)\s+",
        "",
        text.strip(),
        flags=re.IGNORECASE,
    )[:120]
    scope_start = target_date.isoformat()
    scope_end = scope_start
    if "semana" in lowered:
        scope_start = (now.date() - timedelta(days=now.weekday())).isoformat()
        scope_end = (date.fromisoformat(scope_start) + timedelta(days=6)).isoformat()
    return _normalize_interpretation(
        {
            "command_type": command,
            "title": title,
            "target_query": title,
            "date": target_date.isoformat(),
            "time": parsed_time,
            "duration_min": 30,
            "recurrence": recurrence,
            "scope": {"start_date": scope_start, "end_date": scope_end},
            "confidence": 0.35,
        },
        text,
    )


def interpret_schedule_input(text: str) -> dict:
    prefs = get_schedule_preferences()
    prompt = CALENDAR_INPUT_PROMPT.format(
        now_local=_now_local().isoformat(timespec="minutes"),
        timezone=prefs.get("timezone") or "America/Lima",
        text=text.strip(),
    )
    try:
        model = get_chat_model(temperature=0.1, context_window=8192, purpose="classification")
        response = model.invoke([HumanMessage(content=sanitize_text_for_remote_llm(prompt))])
        parsed = _parse_json_object(restore_local_aliases(content_to_text(response.content)))
        if parsed:
            return _normalize_interpretation(parsed, text)
    except Exception as exc:
        log.warning("calendar_interpretation_fallback", error=str(exc))
    return _fallback_interpretation(text)


def _combine_datetime(day: str, clock: str) -> datetime:
    return datetime.combine(date.fromisoformat(day), time.fromisoformat(clock))


def _duration_from_item(item: dict, default: int = 30) -> int:
    try:
        start = datetime.fromisoformat(item["start_at"])
        end = datetime.fromisoformat(item["end_at"])
        return max(5, int((end - start).total_seconds() / 60))
    except (KeyError, TypeError, ValueError):
        return default


def find_open_slot(
    target_date: str,
    duration_min: int,
    *,
    preferred_time: str | None = None,
    ignore_item_ids: set[int] | None = None,
) -> tuple[str, str] | None:
    prefs = get_schedule_preferences()
    day_start = _clean_time(prefs.get("day_start_time")) or "08:00"
    day_end = _clean_time(prefs.get("day_end_time")) or "23:00"
    buffer_min = int(prefs.get("transition_buffer_min") or 0)
    items = get_calendar_items(target_date, target_date)
    ignored = ignore_item_ids or set()
    occupied: list[tuple[datetime, datetime]] = []
    scheduled_minutes = 0
    for item in items:
        if item.get("id") in ignored or not item.get("start_at") or not item.get("end_at"):
            continue
        try:
            start = datetime.fromisoformat(item["start_at"])
            end = datetime.fromisoformat(item["end_at"])
        except ValueError:
            continue
        occupied.append((start - timedelta(minutes=buffer_min), end + timedelta(minutes=buffer_min)))
        scheduled_minutes += max(0, int((end - start).total_seconds() / 60))
    if scheduled_minutes + duration_min > int(prefs.get("max_scheduled_min_per_day") or 480):
        return None

    lower = _combine_datetime(target_date, day_start)
    upper = _combine_datetime(target_date, day_end)
    now = _now_local()
    if lower.date() == now.date():
        rounded = now.replace(second=0, microsecond=0) + timedelta(minutes=15)
        rounded = rounded.replace(minute=(rounded.minute // 15) * 15)
        lower = max(lower, rounded)
    if preferred_time:
        preferred = _combine_datetime(target_date, preferred_time)
        candidates = [preferred]
    else:
        focus_start = _clean_time(prefs.get("focus_window_start"))
        first = max(lower, _combine_datetime(target_date, focus_start)) if focus_start else lower
        candidates = []
        cursor = first
        while cursor + timedelta(minutes=duration_min) <= upper:
            candidates.append(cursor)
            cursor += timedelta(minutes=15)
        cursor = lower
        while cursor < first and cursor + timedelta(minutes=duration_min) <= upper:
            candidates.append(cursor)
            cursor += timedelta(minutes=15)

    for start in candidates:
        end = start + timedelta(minutes=duration_min)
        if start < lower or end > upper:
            continue
        if all(end <= busy_start or start >= busy_end for busy_start, busy_end in occupied):
            return start.isoformat(timespec="minutes"), end.isoformat(timespec="minutes")
    return None


def _find_slot_across_days(
    first_date: str,
    duration_min: int,
    *,
    preferred_time: str | None = None,
    horizon_days: int = 14,
    due_date: str | None = None,
    ignore_item_ids: set[int] | None = None,
) -> tuple[str, str] | None:
    start_day = date.fromisoformat(first_date)
    last_day = start_day + timedelta(days=max(0, horizon_days))
    if due_date:
        last_day = min(last_day, date.fromisoformat(due_date))
    cursor = start_day
    while cursor <= last_day:
        slot = find_open_slot(
            cursor.isoformat(),
            duration_min,
            preferred_time=preferred_time,
            ignore_item_ids=ignore_item_ids,
        )
        if slot:
            return slot
        cursor += timedelta(days=1)
    return None


def parse_cadence_text(text: str | None) -> dict | None:
    if not text:
        return None
    lowered = text.lower()
    days = sorted({index for name, index in DAY_NAMES.items() if name in lowered})
    if any(phrase in lowered for phrase in ["cada dia", "cada día", "todos los dias", "todos los días", "diario", "daily"]):
        return {"frequency": "daily", "interval": 1, "days_of_week": []}
    month_match = re.search(r"(?:dia|día)\s+(\d{1,2}).*(?:mes|mensual)", lowered)
    if "mensual" in lowered or "cada mes" in lowered or month_match:
        return {
            "frequency": "monthly",
            "interval": 1,
            "days_of_week": [],
            "day_of_month": _clamp_int(month_match.group(1), 1, 31) if month_match else None,
        }
    count_match = re.search(r"(\d+)\s*(?:x|veces?)\s*(?:por|a la)?\s*semana", lowered)
    if days or count_match or "semanal" in lowered or "cada semana" in lowered:
        return {
            "frequency": "weekly",
            "interval": 1,
            "days_of_week": days,
            "times_per_week": _clamp_int(count_match.group(1), 1, 7) if count_match else (len(days) or 1),
        }
    return None


def _series_occurs_on(series: dict, day: date) -> bool:
    recurrence = series.get("recurrence") or {}
    first = date.fromisoformat(series["first_date"])
    if day < first:
        return False
    until = _clean_iso_date(series.get("until_date") or recurrence.get("until"))
    if until and day > date.fromisoformat(until):
        return False
    frequency = recurrence.get("frequency")
    interval = int(recurrence.get("interval") or 1)
    if frequency == "daily":
        return (day - first).days % interval == 0
    if frequency == "weekly":
        week_index = (day - first).days // 7
        if week_index % interval != 0:
            return False
        days = recurrence.get("days_of_week") or []
        if not days:
            count = int(recurrence.get("times_per_week") or 1)
            defaults = [0, 2, 4, 1, 3, 5, 6]
            days = sorted(defaults[:count])
        return day.weekday() in days
    if frequency == "monthly":
        months = (day.year - first.year) * 12 + day.month - first.month
        target_day = int(recurrence.get("day_of_month") or first.day)
        return months % interval == 0 and day.day == min(target_day, 28 if day.month == 2 else 30 if day.month in {4, 6, 9, 11} else 31)
    return False


def materialize_recurring_items(start_date: str, end_date: str) -> int:
    created = 0
    for series in get_active_calendar_series():
        cursor = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
        while cursor <= end:
            if _series_occurs_on(series, cursor):
                existing_for_day = [
                    item
                    for item in get_calendar_items(
                        cursor.isoformat(),
                        cursor.isoformat(),
                        include_cancelled=True,
                    )
                    if item.get("series_id") == series.get("id")
                ]
                if existing_for_day:
                    cursor += timedelta(days=1)
                    continue
                preferred = _clean_time(series.get("preferred_time"))
                duration = int(series.get("duration_min") or 30)
                slot = _find_slot_across_days(
                    cursor.isoformat(),
                    duration,
                    preferred_time=preferred,
                    horizon_days=0,
                )
                if not slot and preferred and series.get("flexibility") != "fixed":
                    slot = _find_slot_across_days(
                        cursor.isoformat(),
                        duration,
                        horizon_days=0,
                    )
                if slot:
                    before_count = len(get_calendar_items(cursor.isoformat(), cursor.isoformat(), include_cancelled=True))
                    insert_calendar_item(
                        {
                            "series_id": series["id"],
                            "title": series["title"],
                            "description": series.get("description"),
                            "item_type": series.get("item_type") or "routine",
                            "start_at": slot[0],
                            "end_at": slot[1],
                            "source_kind": series.get("source_kind"),
                            "source_id": series.get("source_id"),
                            "source_key": series.get("source_key"),
                            "goal_id": series.get("goal_id"),
                            "domain_code": series.get("domain_code"),
                            "priority": series.get("priority"),
                            "flexibility": series.get("flexibility"),
                            "energy_required": series.get("energy_required"),
                            "location": series.get("location"),
                            "rationale": "Instancia generada desde una actividad recurrente.",
                        }
                    )
                    after_count = len(get_calendar_items(cursor.isoformat(), cursor.isoformat(), include_cancelled=True))
                    if after_count > before_count:
                        created += 1
            cursor += timedelta(days=1)
    return created


def _fingerprint(*parts: Any) -> str:
    normalized = "|".join(str(part or "") for part in parts)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:32]


def _infer_relative_date(text: str) -> str | None:
    lowered = (text or "").lower()
    today = _now_local().date()
    if "pasado mañana" in lowered or "pasado manana" in lowered:
        return (today + timedelta(days=2)).isoformat()
    if "mañana" in lowered or "manana" in lowered:
        return (today + timedelta(days=1)).isoformat()
    if re.search(r"\bhoy\b", lowered):
        return today.isoformat()
    mentioned_days = [index for name, index in DAY_NAMES.items() if re.search(rf"\b{re.escape(name)}\b", lowered)]
    if mentioned_days:
        delta = (mentioned_days[0] - today.weekday()) % 7
        if delta == 0 and any(word in lowered for word in ["proximo", "próximo", "siguiente"]):
            delta = 7
        return (today + timedelta(days=delta)).isoformat()
    return None


def create_diary_action_suggestion(
    *,
    semantic_unit_id: int,
    diary_entry_id: int | None,
    content: str,
    metadata: dict | None = None,
) -> dict:
    metadata = metadata or {}
    duration = _clamp_int(metadata.get("duration_min"), 5, 720, 30) or 30
    target_date = (
        _clean_iso_date(metadata.get("date") or metadata.get("due_date"))
        or _infer_relative_date(content)
        or _now_local().date().isoformat()
    )
    preferred_time = _clean_time(metadata.get("time"))
    if preferred_time and metadata.get("flexibility") == "fixed":
        fixed_start = _combine_datetime(target_date, preferred_time)
        slot = (
            fixed_start.isoformat(timespec="minutes"),
            (fixed_start + timedelta(minutes=duration)).isoformat(timespec="minutes"),
        )
    else:
        slot = _find_slot_across_days(
            target_date,
            duration,
            preferred_time=preferred_time,
            due_date=_clean_iso_date(metadata.get("due_date")),
        )
    recurrence = _normalize_recurrence(metadata.get("recurrence"))
    title = str(metadata.get("action_title") or content).strip()[:120]
    return insert_calendar_suggestion(
        {
            "proposal_type": "create_series" if recurrence else "create_item",
            "source_kind": "diary",
            "source_id": diary_entry_id,
            "source_key": f"semantic_unit:{semantic_unit_id}",
            "fingerprint": _fingerprint("diary-action", semantic_unit_id),
            "title": title,
            "description": content,
            "proposed_start_at": slot[0] if slot else None,
            "proposed_end_at": slot[1] if slot else None,
            "due_at": metadata.get("due_date"),
            "duration_min": duration,
            "item_type": metadata.get("item_type") or "task",
            "recurrence": recurrence,
            "priority": _clamp_int(metadata.get("priority"), 1, 5, 3),
            "flexibility": metadata.get("flexibility") or "movable",
            "location": metadata.get("place_name"),
            "confidence": metadata.get("confidence") or 0.7,
            "rationale": "Accion detectada dentro de una entrada del diario. Requiere tu aprobacion.",
            "payload": {"semantic_unit_id": semantic_unit_id},
        }
    )


def _domain_from_goal(goal: dict) -> str | None:
    return goal.get("domain_code") or goal.get("domain") or None


def _suggest_goal_contributions() -> int:
    created = 0
    today = _now_local().date().isoformat()
    for goal in get_goals(status="active", limit=500):
        if goal.get("node_type") not in {"system", "action"}:
            continue
        cadence = parse_cadence_text(goal.get("cadence_text"))
        duration = int(goal.get("time_cost_min") or 30)
        source_key = f"goal:{goal['id']}"
        fingerprint = _fingerprint("engine-contribution", source_key)
        if cadence:
            suggestion = {
                "proposal_type": "create_series",
                "recurrence": cadence,
                "proposed_start_at": None,
                "proposed_end_at": None,
                "item_type": "routine",
            }
        else:
            target = _clean_iso_date(goal.get("target_date")) or today
            slot = _find_slot_across_days(today, duration, due_date=target, horizon_days=30)
            suggestion = {
                "proposal_type": "create_item",
                "recurrence": None,
                "proposed_start_at": slot[0] if slot else None,
                "proposed_end_at": slot[1] if slot else None,
                "due_at": target,
                "item_type": "task",
            }
        existing = insert_calendar_suggestion(
            {
                **suggestion,
                "source_kind": "goal",
                "source_id": goal["id"],
                "source_key": source_key,
                "fingerprint": fingerprint,
                "title": goal["title"],
                "description": goal.get("description") or goal.get("why_matters"),
                "duration_min": duration,
                "goal_id": goal["id"],
                "domain_code": _domain_from_goal(goal),
                "priority": _clamp_int(goal.get("importance"), 1, 5, 3),
                "energy_required": goal.get("energy_cost"),
                "flexibility": "movable",
                "confidence": 0.9,
                "rationale": "Convierte una accion o sistema activo de Metas en tiempo real protegido.",
            }
        )
        if existing.get("status") == "pending" and existing.get("created_at", "").startswith(today):
            created += 1
    return created


def _suggest_workout_contribution() -> int:
    profile = get_exercise_profile() or {}
    if not profile:
        return 0
    days_per_week = _clamp_int(profile.get("workout_days_per_week"), 1, 7, 3) or 3
    names = profile.get("schedule_days") or []
    days = sorted({DAY_NAMES[str(name).lower()] for name in names if str(name).lower() in DAY_NAMES})
    recurrence = {
        "frequency": "weekly",
        "interval": 1,
        "days_of_week": days,
        "times_per_week": days_per_week,
    }
    duration = int(profile.get("optimal_session_min") or profile.get("time_per_workout_min") or 45)
    fingerprint = _fingerprint("engine-contribution", "exercise:primary-routine")
    insert_calendar_suggestion(
        {
            "proposal_type": "create_series",
            "source_kind": "exercise",
            "source_id": profile.get("id"),
            "source_key": "exercise:primary-routine",
            "fingerprint": fingerprint,
            "title": "Entrenamiento para ganar musculo",
            "description": f"Plan principal de {duration} min. El motor de Cuerpo mantiene un rescate minimo para dias dificiles.",
            "duration_min": duration,
            "item_type": "routine",
            "recurrence": recurrence,
            "priority": 4,
            "energy_required": 4,
            "flexibility": "movable",
            "location": profile.get("preferred_location"),
            "confidence": 0.95,
            "rationale": "Protege la frecuencia semanal definida en Cuerpo sin convertir un fallo aislado en deuda moral.",
            "payload": {"minimum_duration_min": profile.get("minimum_session_min") or 12},
        }
    )
    return 1


def _suggest_finance_contributions() -> int:
    profile = get_finance_profile() or {}
    created = 0
    today = _now_local().date()
    for index, expense in enumerate(profile.get("fixed_expenses") or []):
        due_day = _clamp_int(expense.get("due_day") or expense.get("dia_pago"), 1, 31)
        if not due_day:
            continue
        name = expense.get("name") or expense.get("nombre") or f"Pago fijo {index + 1}"
        amount = expense.get("amount") or expense.get("monto")
        source_key = f"finance:fixed:{index}:{name}"
        insert_calendar_suggestion(
            {
                "proposal_type": "create_series",
                "source_kind": "finance",
                "source_id": profile.get("id"),
                "source_key": source_key,
                "fingerprint": _fingerprint("engine-contribution", source_key),
                "title": f"Pagar {name}",
                "description": f"Monto registrado: {amount} {profile.get('currency') or 'PEN'}" if amount is not None else None,
                "duration_min": 15,
                "item_type": "reminder",
                "recurrence": {"frequency": "monthly", "interval": 1, "days_of_week": [], "day_of_month": due_day},
                "priority": 5,
                "flexibility": "fixed",
                "confidence": 0.95,
                "rationale": "Fecha de pago detectada en el perfil financiero.",
                "payload": {"first_date": date(today.year, today.month, min(due_day, 28)).isoformat()},
            }
        )
        created += 1
    return created


def sync_engine_suggestions() -> dict:
    return {
        "goals": _suggest_goal_contributions(),
        "exercise": _suggest_workout_contribution(),
        "finance": _suggest_finance_contributions(),
    }


def approve_calendar_suggestion(suggestion_id: int, edits: dict | None = None) -> dict:
    suggestion = get_calendar_suggestion(suggestion_id)
    if not suggestion or suggestion.get("status") != "pending":
        raise ValueError("La sugerencia no existe o ya fue resuelta.")
    merged = {**suggestion, **(edits or {})}
    recurrence = (edits or {}).get("recurrence", suggestion.get("recurrence"))
    if merged.get("proposal_type") == "create_series" or recurrence:
        start_at = merged.get("proposed_start_at")
        first_date = (edits or {}).get("first_date") or (start_at[:10] if start_at else _now_local().date().isoformat())
        preferred_time = (edits or {}).get("preferred_time") or (start_at[11:16] if start_at else None)
        series = insert_calendar_series(
            {
                "title": merged.get("title"),
                "description": merged.get("description"),
                "item_type": merged.get("item_type") or "routine",
                "recurrence": recurrence,
                "preferred_time": preferred_time,
                "duration_min": merged.get("duration_min") or 30,
                "first_date": first_date,
                "until_date": (recurrence or {}).get("until"),
                "source_kind": merged.get("source_kind"),
                "source_id": merged.get("source_id"),
                "source_key": merged.get("source_key"),
                "goal_id": merged.get("goal_id"),
                "domain_code": merged.get("domain_code"),
                "priority": merged.get("priority"),
                "flexibility": merged.get("flexibility"),
                "energy_required": merged.get("energy_required"),
                "location": merged.get("location"),
            }
        )
        materialize_recurring_items(first_date, (date.fromisoformat(first_date) + timedelta(days=56)).isoformat())
        result = {"series": series}
    else:
        duration = int(merged.get("duration_min") or 30)
        start_at = merged.get("proposed_start_at")
        end_at = merged.get("proposed_end_at")
        if start_at and not end_at:
            end_at = (datetime.fromisoformat(start_at) + timedelta(minutes=duration)).isoformat(timespec="minutes")
        item = insert_calendar_item(
            {
                "title": merged.get("title"),
                "description": merged.get("description"),
                "item_type": merged.get("item_type"),
                "start_at": start_at,
                "end_at": end_at,
                "due_at": merged.get("due_at"),
                "source_kind": merged.get("source_kind"),
                "source_id": merged.get("source_id"),
                "source_key": merged.get("source_key"),
                "goal_id": merged.get("goal_id"),
                "domain_code": merged.get("domain_code"),
                "priority": merged.get("priority"),
                "flexibility": merged.get("flexibility"),
                "energy_required": merged.get("energy_required"),
                "location": merged.get("location"),
                "rationale": merged.get("rationale"),
            }
        )
        result = {"item": item}
    resolve_calendar_suggestion(suggestion_id, "approved")
    return result


def reject_calendar_suggestion(suggestion_id: int) -> dict:
    suggestion = resolve_calendar_suggestion(suggestion_id, "rejected")
    if not suggestion:
        raise ValueError("Sugerencia no encontrada.")
    return suggestion


def _create_from_interpretation(parsed: dict, input_id: int) -> dict:
    target_date = parsed.get("date") or _now_local().date().isoformat()
    duration = int(parsed.get("duration_min") or get_schedule_preferences().get("default_task_duration_min") or 30)
    recurrence = parsed.get("recurrence")
    if recurrence:
        series = insert_calendar_series(
            {
                "title": parsed.get("title") or "Rutina",
                "description": parsed.get("description"),
                "item_type": parsed.get("item_type") or "routine",
                "recurrence": recurrence,
                "preferred_time": parsed.get("time"),
                "duration_min": duration,
                "first_date": target_date,
                "until_date": recurrence.get("until"),
                "source_kind": "direct",
                "priority": parsed.get("priority"),
                "flexibility": parsed.get("flexibility"),
                "energy_required": parsed.get("energy_required"),
                "location": parsed.get("location"),
            }
        )
        materialize_recurring_items(target_date, (date.fromisoformat(target_date) + timedelta(days=56)).isoformat())
        return {"message": "Actividad recurrente creada.", "series": series}
    if parsed.get("time"):
        requested_start = _combine_datetime(target_date, parsed["time"])
        slot = (
            requested_start.isoformat(timespec="minutes"),
            (requested_start + timedelta(minutes=duration)).isoformat(timespec="minutes"),
        )
    else:
        slot = _find_slot_across_days(
            target_date,
            duration,
            due_date=parsed.get("due_date"),
        )
    end_at = None
    if slot and parsed.get("end_time"):
        end_at = _combine_datetime(slot[0][:10], parsed["end_time"]).isoformat(timespec="minutes")
    item = insert_calendar_item(
        {
            "title": parsed.get("title") or "Actividad",
            "description": parsed.get("description"),
            "item_type": parsed.get("item_type"),
            "start_at": slot[0] if slot else None,
            "end_at": end_at or (slot[1] if slot else None),
            "due_at": parsed.get("due_date"),
            "source_kind": "direct",
            "priority": parsed.get("priority"),
            "flexibility": "fixed" if parsed.get("time") else parsed.get("flexibility"),
            "energy_required": parsed.get("energy_required"),
            "location": parsed.get("location"),
            "rationale": "Creado desde una instruccion directa.",
        },
        schedule_input_id=input_id,
    )
    message = "Actividad agendada." if slot else "Actividad guardada sin hora porque no encontre un espacio realista."
    return {"message": message, "item": item}


def _target_window(parsed: dict) -> tuple[str, str]:
    now = _now_local().date()
    scope = parsed.get("scope") or {}
    start = scope.get("start_date") or (now - timedelta(days=7)).isoformat()
    end = scope.get("end_date") or (now + timedelta(days=90)).isoformat()
    return start, end


def _find_target(parsed: dict) -> list[dict]:
    query = parsed.get("target_query") or parsed.get("title") or ""
    if not query:
        return []
    start, end = _target_window(parsed)
    return find_calendar_item_candidates(query, start, end)


def _reschedule_target(item: dict, parsed: dict, input_id: int) -> dict:
    duration = parsed.get("duration_min") or _duration_from_item(item)
    target_date = parsed.get("date") or item.get("start_at", "")[:10] or _now_local().date().isoformat()
    slot = _find_slot_across_days(
        target_date,
        int(duration),
        preferred_time=parsed.get("time"),
        ignore_item_ids={item["id"]},
    )
    if not slot:
        return {"message": "No encontre un espacio libre para moverla.", "item": item, "needs_review": True}
    updated = update_calendar_item(
        item["id"],
        {"start_at": slot[0], "end_at": slot[1]},
        reason=parsed.get("original_text"),
        schedule_input_id=input_id,
    )
    return {"message": "Actividad reprogramada.", "item": updated}


def replan_calendar_window(
    start_date: str,
    end_date: str,
    *,
    source_kind: str | None = None,
    schedule_input_id: int | None = None,
    reason: str | None = None,
) -> dict:
    items = get_calendar_items(start_date, end_date)
    movable = [
        item for item in items
        if item.get("status") == "planned"
        and item.get("flexibility") != "fixed"
        and (not source_kind or item.get("source_kind") == source_kind)
    ]
    movable.sort(key=lambda item: (-int(item.get("priority") or 3), item.get("start_at") or ""))
    ignore_ids = {int(item["id"]) for item in movable}
    changed = []
    cursor_date = date.fromisoformat(start_date)
    final_date = date.fromisoformat(end_date)
    for item in movable:
        duration = _duration_from_item(item)
        original_day = date.fromisoformat(item["start_at"][:10]) if item.get("start_at") else cursor_date
        preferred_day = max(cursor_date, min(original_day, final_date))
        slot = _find_slot_across_days(
            preferred_day.isoformat(),
            duration,
            horizon_days=(final_date - preferred_day).days,
            ignore_item_ids=ignore_ids,
        )
        if not slot:
            continue
        ignore_ids.discard(int(item["id"]))
        if slot[0] != item.get("start_at") or slot[1] != item.get("end_at"):
            updated = update_calendar_item(
                item["id"],
                {"start_at": slot[0], "end_at": slot[1]},
                reason=reason or "Replanificacion solicitada.",
                schedule_input_id=schedule_input_id,
            )
            changed.append(updated)
    return {"changed": changed, "changed_count": len(changed), "considered_count": len(movable)}


def _update_recurring_target(parsed: dict) -> dict:
    query = (parsed.get("target_query") or parsed.get("title") or "").lower()
    candidates = [series for series in get_active_calendar_series() if query and query in series.get("title", "").lower()]
    if len(candidates) != 1:
        return {"needs_review": True, "message": "Necesito una actividad recurrente mas especifica.", "candidates": candidates[:10]}
    updates = {}
    if parsed.get("time"):
        updates["preferred_time"] = parsed["time"]
    if parsed.get("duration_min"):
        updates["duration_min"] = parsed["duration_min"]
    if parsed.get("recurrence"):
        updates["recurrence"] = parsed["recurrence"]
    series = update_calendar_series(candidates[0]["id"], updates)
    return {"message": "Rutina actualizada.", "series": series}


def process_schedule_input(
    text: str,
    *,
    input_mode: str = "text",
    audio_path: str | None = None,
) -> dict:
    cleaned = (text or "").strip()
    if not cleaned:
        raise ValueError("La instruccion esta vacia.")
    input_id = insert_schedule_input(cleaned, input_mode=input_mode, audio_path=audio_path)
    parsed = interpret_schedule_input(cleaned)
    command = parsed["command_type"]
    status = "processed"
    try:
        if command == "create":
            result = _create_from_interpretation(parsed, input_id)
        elif command in {"reschedule", "cancel", "complete"}:
            candidates = _find_target(parsed)
            if len(candidates) != 1:
                status = "needs_review"
                result = {
                    "needs_review": True,
                    "message": "No pude identificar una sola actividad. Elige una de las candidatas o se mas especifico.",
                    "candidates": candidates,
                }
            elif command == "reschedule":
                result = _reschedule_target(candidates[0], parsed, input_id)
            else:
                next_status = "cancelled" if command == "cancel" else "completed"
                item = update_calendar_item(
                    candidates[0]["id"],
                    {"status": next_status},
                    reason=cleaned,
                    schedule_input_id=input_id,
                )
                result = {"message": "Actividad cancelada." if command == "cancel" else "Actividad completada.", "item": item}
        elif command == "rearrange":
            start, end = _target_window(parsed)
            replanned = replan_calendar_window(
                start,
                end,
                source_kind=(parsed.get("scope") or {}).get("source_kind"),
                schedule_input_id=input_id,
                reason=cleaned,
            )
            result = {"message": f"Reorganicé {replanned['changed_count']} actividades movibles.", **replanned}
        elif command == "update_series":
            result = _update_recurring_target(parsed)
            if result.get("needs_review"):
                status = "needs_review"
        else:
            status = "needs_review"
            result = {
                "needs_review": True,
                "message": "No detecté una acción de agenda concreta. Puedes decir qué, cuándo o qué parte quieres reorganizar.",
            }
    except Exception as exc:
        log.exception("calendar_command_failed", command=command, error=str(exc))
        finish_schedule_input(
            input_id,
            command_type=command,
            interpretation=parsed,
            status="failed",
            result={"error": str(exc)},
        )
        raise
    finish_schedule_input(
        input_id,
        command_type=command,
        interpretation=parsed,
        status=status,
        result=result,
    )
    return {"input_id": input_id, "interpretation": parsed, "status": status, **result}


def build_calendar_dashboard(week_start: str | None = None) -> dict:
    today = _now_local().date()
    if week_start:
        start = date.fromisoformat(week_start)
    else:
        start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=6)
    materialize_recurring_items(start.isoformat(), (end + timedelta(days=28)).isoformat())
    sync_engine_suggestions()
    items = get_calendar_items(start.isoformat(), end.isoformat())
    prefs = get_schedule_preferences()
    minutes_by_day: dict[str, int] = {}
    source_counts: dict[str, int] = {}
    goal_aligned = 0
    intervals_by_day: dict[str, list[tuple[datetime, datetime, int]]] = {}
    for item in items:
        day = item.get("start_at", "")[:10]
        minutes_by_day[day] = minutes_by_day.get(day, 0) + _duration_from_item(item, 0)
        source = item.get("source_kind") or "direct"
        source_counts[source] = source_counts.get(source, 0) + 1
        if item.get("goal_id"):
            goal_aligned += 1
        if item.get("status") == "planned" and item.get("start_at") and item.get("end_at"):
            try:
                intervals_by_day.setdefault(day, []).append(
                    (datetime.fromisoformat(item["start_at"]), datetime.fromisoformat(item["end_at"]), int(item["id"]))
                )
            except ValueError:
                pass
    conflict_ids: set[int] = set()
    for intervals in intervals_by_day.values():
        intervals.sort(key=lambda value: value[0])
        for index, current in enumerate(intervals):
            for other in intervals[index + 1:]:
                if other[0] >= current[1]:
                    break
                conflict_ids.update({current[2], other[2]})
    max_minutes = int(prefs.get("max_scheduled_min_per_day") or 480)
    return {
        "week_start": start.isoformat(),
        "week_end": end.isoformat(),
        "today": today.isoformat(),
        "items": items,
        "unscheduled": get_unscheduled_items(),
        "suggestions": get_calendar_suggestions("pending"),
        "preferences": prefs,
        "series": get_active_calendar_series(),
        "health": {
            "minutes_by_day": minutes_by_day,
            "overloaded_days": [day for day, minutes in minutes_by_day.items() if minutes > max_minutes],
            "source_counts": source_counts,
            "goal_aligned_count": goal_aligned,
            "planned_count": len(items),
            "conflict_item_ids": sorted(conflict_ids),
        },
    }
