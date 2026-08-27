from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime
from typing import Any

from backend.config import DB_PATH


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _json_load(raw: str | None, fallback: Any) -> Any:
    try:
        return json.loads(raw or "")
    except (TypeError, json.JSONDecodeError):
        return fallback


def _normalize_item(row: sqlite3.Row | dict | None) -> dict | None:
    if row is None:
        return None
    result = dict(row)
    result["metadata"] = _json_load(result.get("metadata_json"), {})
    return result


def _normalize_series(row: sqlite3.Row | dict | None) -> dict | None:
    if row is None:
        return None
    result = dict(row)
    result["recurrence"] = _json_load(result.get("recurrence_json"), {})
    return result


def _normalize_suggestion(row: sqlite3.Row | dict | None) -> dict | None:
    if row is None:
        return None
    result = dict(row)
    result["recurrence"] = _json_load(result.get("recurrence_json"), None)
    result["payload"] = _json_load(result.get("payload_json"), {})
    return result


def get_schedule_preferences() -> dict:
    conn = _conn()
    row = conn.execute("SELECT * FROM schedule_preferences WHERE id = 1").fetchone()
    conn.close()
    if not row:
        return {
            "id": 1,
            "timezone": "America/Lima",
            "day_start_time": "08:00",
            "day_end_time": "23:00",
            "focus_window_start": "09:00",
            "focus_window_end": "13:00",
            "default_task_duration_min": 30,
            "transition_buffer_min": 10,
            "max_scheduled_min_per_day": 480,
            "preferred_work_days": [0, 1, 2, 3, 4],
            "protected_windows": [],
        }
    result = dict(row)
    result["preferred_work_days"] = _json_load(result.get("preferred_work_days_json"), [0, 1, 2, 3, 4])
    result["protected_windows"] = _json_load(result.get("protected_windows_json"), [])
    return result


def update_schedule_preferences(updates: dict) -> dict:
    allowed = {
        "timezone", "day_start_time", "day_end_time", "focus_window_start",
        "focus_window_end", "default_task_duration_min", "transition_buffer_min",
        "max_scheduled_min_per_day", "notes",
    }
    normalized = {key: value for key, value in updates.items() if key in allowed}
    if "preferred_work_days" in updates:
        normalized["preferred_work_days_json"] = json.dumps(updates.get("preferred_work_days") or [])
    if "protected_windows" in updates:
        normalized["protected_windows_json"] = json.dumps(updates.get("protected_windows") or [], ensure_ascii=False)
    if normalized:
        normalized["updated_at"] = datetime.now().isoformat(timespec="seconds")
        conn = _conn()
        assignments = ", ".join(f"{field} = ?" for field in normalized)
        conn.execute(
            f"UPDATE schedule_preferences SET {assignments} WHERE id = 1",
            list(normalized.values()),
        )
        conn.commit()
        conn.close()
    return get_schedule_preferences()


def insert_schedule_input(
    raw_text: str,
    input_mode: str = "text",
    audio_path: str | None = None,
) -> int:
    conn = _conn()
    cursor = conn.execute(
        "INSERT INTO schedule_inputs (input_mode, raw_text, audio_path) VALUES (?, ?, ?)",
        (input_mode, raw_text, audio_path),
    )
    input_id = int(cursor.lastrowid)
    conn.commit()
    conn.close()
    return input_id


def finish_schedule_input(
    input_id: int,
    *,
    command_type: str,
    interpretation: dict,
    status: str,
    result: dict,
) -> None:
    conn = _conn()
    conn.execute(
        """UPDATE schedule_inputs
           SET command_type = ?, interpretation_json = ?, status = ?, result_json = ?,
               processed_at = datetime('now')
           WHERE id = ?""",
        (
            command_type,
            json.dumps(interpretation, ensure_ascii=False),
            status,
            json.dumps(result, ensure_ascii=False),
            input_id,
        ),
    )
    conn.commit()
    conn.close()


def insert_calendar_item(data: dict, schedule_input_id: int | None = None) -> dict:
    fields = [
        "series_id", "title", "description", "item_type", "start_at", "end_at",
        "due_at", "all_day", "status", "source_kind", "source_id", "source_key",
        "goal_id", "domain_code", "priority", "flexibility", "energy_required",
        "location", "rationale", "metadata_json",
    ]
    values = {
        "series_id": data.get("series_id"),
        "title": str(data.get("title") or "Actividad").strip(),
        "description": data.get("description"),
        "item_type": data.get("item_type") or "task",
        "start_at": data.get("start_at"),
        "end_at": data.get("end_at"),
        "due_at": data.get("due_at"),
        "all_day": 1 if data.get("all_day") else 0,
        "status": data.get("status") or "planned",
        "source_kind": data.get("source_kind") or "direct",
        "source_id": data.get("source_id"),
        "source_key": data.get("source_key"),
        "goal_id": data.get("goal_id"),
        "domain_code": data.get("domain_code"),
        "priority": int(data.get("priority") or 3),
        "flexibility": data.get("flexibility") or "movable",
        "energy_required": data.get("energy_required"),
        "location": data.get("location"),
        "rationale": data.get("rationale"),
        "metadata_json": json.dumps(data.get("metadata") or {}, ensure_ascii=False),
    }
    conn = _conn()
    try:
        cursor = conn.execute(
            f"INSERT INTO calendar_items ({', '.join(fields)}) VALUES ({', '.join('?' for _ in fields)})",
            [values[field] for field in fields],
        )
        item_id = int(cursor.lastrowid)
    except sqlite3.IntegrityError:
        if data.get("series_id") and data.get("start_at"):
            row = conn.execute(
                "SELECT * FROM calendar_items WHERE series_id = ? AND start_at = ?",
                (data["series_id"], data["start_at"]),
            ).fetchone()
            conn.close()
            if row:
                return _normalize_item(row) or {}
        conn.close()
        raise
    row = conn.execute("SELECT * FROM calendar_items WHERE id = ?", (item_id,)).fetchone()
    after = _normalize_item(row) or {}
    conn.execute(
        """INSERT INTO calendar_item_history
           (item_id, change_type, before_json, after_json, reason, schedule_input_id)
           VALUES (?, 'created', '{}', ?, ?, ?)""",
        (
            item_id,
            json.dumps(after, ensure_ascii=False),
            data.get("rationale"),
            schedule_input_id,
        ),
    )
    conn.commit()
    conn.close()
    return after


def get_calendar_item(item_id: int) -> dict | None:
    conn = _conn()
    row = conn.execute("SELECT * FROM calendar_items WHERE id = ?", (item_id,)).fetchone()
    conn.close()
    return _normalize_item(row)


def get_calendar_items(
    start_date: str,
    end_date: str,
    *,
    include_cancelled: bool = False,
) -> list[dict]:
    conn = _conn()
    status_clause = "" if include_cancelled else "AND status != 'cancelled'"
    rows = conn.execute(
        f"""SELECT * FROM calendar_items
            WHERE start_at IS NOT NULL
              AND date(start_at) >= date(?) AND date(start_at) <= date(?)
              {status_clause}
            ORDER BY start_at, priority DESC, id""",
        (start_date, end_date),
    ).fetchall()
    conn.close()
    return [_normalize_item(row) or {} for row in rows]


def get_unscheduled_items(limit: int = 50) -> list[dict]:
    conn = _conn()
    rows = conn.execute(
        """SELECT * FROM calendar_items
           WHERE start_at IS NULL AND status = 'planned'
           ORDER BY priority DESC, due_at, created_at LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return [_normalize_item(row) or {} for row in rows]


def update_calendar_item(
    item_id: int,
    updates: dict,
    *,
    reason: str | None = None,
    schedule_input_id: int | None = None,
) -> dict | None:
    allowed = {
        "title", "description", "item_type", "start_at", "end_at", "due_at",
        "all_day", "status", "priority", "flexibility", "energy_required",
        "location", "rationale", "goal_id", "domain_code",
    }
    normalized = {key: value for key, value in updates.items() if key in allowed}
    if "metadata" in updates:
        normalized["metadata_json"] = json.dumps(updates.get("metadata") or {}, ensure_ascii=False)
    conn = _conn()
    before_row = conn.execute("SELECT * FROM calendar_items WHERE id = ?", (item_id,)).fetchone()
    before = _normalize_item(before_row)
    if not before:
        conn.close()
        return None
    if not normalized:
        conn.close()
        return before
    normalized["updated_at"] = datetime.now().isoformat(timespec="seconds")
    if normalized.get("status") == "completed":
        normalized["completed_at"] = datetime.now().isoformat(timespec="seconds")
    assignments = ", ".join(f"{field} = ?" for field in normalized)
    conn.execute(
        f"UPDATE calendar_items SET {assignments} WHERE id = ?",
        [*normalized.values(), item_id],
    )
    after_row = conn.execute("SELECT * FROM calendar_items WHERE id = ?", (item_id,)).fetchone()
    after = _normalize_item(after_row) or {}
    conn.execute(
        """INSERT INTO calendar_item_history
           (item_id, change_type, before_json, after_json, reason, schedule_input_id)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            item_id,
            "status" if "status" in normalized else "updated",
            json.dumps(before, ensure_ascii=False),
            json.dumps(after, ensure_ascii=False),
            reason,
            schedule_input_id,
        ),
    )
    conn.commit()
    conn.close()
    return after


def find_calendar_item_candidates(
    query: str,
    start_date: str,
    end_date: str,
    limit: int = 10,
) -> list[dict]:
    conn = _conn()
    needle = f"%{query.strip()}%"
    rows = conn.execute(
        """SELECT * FROM calendar_items
           WHERE status = 'planned' AND date(start_at) BETWEEN date(?) AND date(?)
             AND (title LIKE ? OR description LIKE ?)
           ORDER BY start_at LIMIT ?""",
        (start_date, end_date, needle, needle, limit),
    ).fetchall()
    conn.close()
    return [_normalize_item(row) or {} for row in rows]


def insert_calendar_series(data: dict) -> dict:
    recurrence = data.get("recurrence") or {}
    conn = _conn()
    cursor = conn.execute(
        """INSERT INTO calendar_series (
               title, description, item_type, recurrence_json, preferred_time, duration_min,
               first_date, until_date, source_kind, source_id, source_key, goal_id,
               domain_code, priority, flexibility, energy_required, location, active
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            str(data.get("title") or "Rutina").strip(),
            data.get("description"),
            data.get("item_type") or "routine",
            json.dumps(recurrence, ensure_ascii=False),
            data.get("preferred_time"),
            int(data.get("duration_min") or 30),
            data.get("first_date") or date.today().isoformat(),
            data.get("until_date"),
            data.get("source_kind") or "direct",
            data.get("source_id"),
            data.get("source_key"),
            data.get("goal_id"),
            data.get("domain_code"),
            int(data.get("priority") or 3),
            data.get("flexibility") or "movable",
            data.get("energy_required"),
            data.get("location"),
            1 if data.get("active", True) else 0,
        ),
    )
    series_id = int(cursor.lastrowid)
    conn.commit()
    row = conn.execute("SELECT * FROM calendar_series WHERE id = ?", (series_id,)).fetchone()
    conn.close()
    return _normalize_series(row) or {}


def get_active_calendar_series() -> list[dict]:
    conn = _conn()
    rows = conn.execute(
        "SELECT * FROM calendar_series WHERE active = 1 ORDER BY priority DESC, id"
    ).fetchall()
    conn.close()
    return [_normalize_series(row) or {} for row in rows]


def update_calendar_series(series_id: int, updates: dict) -> dict | None:
    allowed = {
        "title", "description", "preferred_time", "duration_min", "first_date",
        "until_date", "priority", "flexibility", "energy_required", "location", "active",
    }
    normalized = {key: value for key, value in updates.items() if key in allowed}
    if "recurrence" in updates:
        normalized["recurrence_json"] = json.dumps(updates.get("recurrence") or {}, ensure_ascii=False)
    if normalized:
        normalized["updated_at"] = datetime.now().isoformat(timespec="seconds")
        conn = _conn()
        assignments = ", ".join(f"{field} = ?" for field in normalized)
        conn.execute(
            f"UPDATE calendar_series SET {assignments} WHERE id = ?",
            [*normalized.values(), series_id],
        )
        conn.commit()
        row = conn.execute("SELECT * FROM calendar_series WHERE id = ?", (series_id,)).fetchone()
        conn.close()
        return _normalize_series(row)
    conn = _conn()
    row = conn.execute("SELECT * FROM calendar_series WHERE id = ?", (series_id,)).fetchone()
    conn.close()
    return _normalize_series(row)


def insert_calendar_suggestion(data: dict) -> dict:
    fields = [
        "proposal_type", "source_kind", "source_id", "source_key", "fingerprint",
        "target_item_id", "target_series_id", "title", "description",
        "proposed_start_at", "proposed_end_at", "due_at", "duration_min",
        "item_type", "recurrence_json", "goal_id", "domain_code", "priority",
        "flexibility", "energy_required", "location", "confidence", "rationale",
        "payload_json",
    ]
    values = {
        "proposal_type": data.get("proposal_type") or "create_item",
        "source_kind": data.get("source_kind") or "diary",
        "source_id": data.get("source_id"),
        "source_key": data.get("source_key"),
        "fingerprint": data["fingerprint"],
        "target_item_id": data.get("target_item_id"),
        "target_series_id": data.get("target_series_id"),
        "title": str(data.get("title") or "Actividad sugerida").strip(),
        "description": data.get("description"),
        "proposed_start_at": data.get("proposed_start_at"),
        "proposed_end_at": data.get("proposed_end_at"),
        "due_at": data.get("due_at"),
        "duration_min": data.get("duration_min"),
        "item_type": data.get("item_type") or "task",
        "recurrence_json": json.dumps(data.get("recurrence"), ensure_ascii=False) if data.get("recurrence") else None,
        "goal_id": data.get("goal_id"),
        "domain_code": data.get("domain_code"),
        "priority": int(data.get("priority") or 3),
        "flexibility": data.get("flexibility") or "movable",
        "energy_required": data.get("energy_required"),
        "location": data.get("location"),
        "confidence": data.get("confidence"),
        "rationale": data.get("rationale"),
        "payload_json": json.dumps(data.get("payload") or {}, ensure_ascii=False),
    }
    conn = _conn()
    conn.execute(
        f"INSERT OR IGNORE INTO calendar_suggestions ({', '.join(fields)}) VALUES ({', '.join('?' for _ in fields)})",
        [values[field] for field in fields],
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM calendar_suggestions WHERE fingerprint = ?",
        (data["fingerprint"],),
    ).fetchone()
    conn.close()
    return _normalize_suggestion(row) or {}


def get_calendar_suggestions(status: str = "pending", limit: int = 100) -> list[dict]:
    conn = _conn()
    rows = conn.execute(
        """SELECT * FROM calendar_suggestions WHERE status = ?
           ORDER BY priority DESC, created_at DESC LIMIT ?""",
        (status, limit),
    ).fetchall()
    conn.close()
    return [_normalize_suggestion(row) or {} for row in rows]


def get_calendar_suggestion(suggestion_id: int) -> dict | None:
    conn = _conn()
    row = conn.execute(
        "SELECT * FROM calendar_suggestions WHERE id = ?",
        (suggestion_id,),
    ).fetchone()
    conn.close()
    return _normalize_suggestion(row)


def resolve_calendar_suggestion(suggestion_id: int, status: str) -> dict | None:
    if status not in {"approved", "rejected"}:
        raise ValueError("Suggestion status must be approved or rejected")
    conn = _conn()
    conn.execute(
        """UPDATE calendar_suggestions
           SET status = ?, resolved_at = datetime('now') WHERE id = ?""",
        (status, suggestion_id),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM calendar_suggestions WHERE id = ?",
        (suggestion_id,),
    ).fetchone()
    conn.close()
    return _normalize_suggestion(row)


def get_upcoming_calendar_items(days: int = 7, limit: int = 20) -> list[dict]:
    conn = _conn()
    rows = conn.execute(
        """SELECT * FROM calendar_items
           WHERE status = 'planned' AND datetime(start_at) >= datetime('now', 'localtime')
             AND datetime(start_at) <= datetime('now', 'localtime', ?)
           ORDER BY datetime(start_at) LIMIT ?""",
        (f"+{max(1, days)} days", limit),
    ).fetchall()
    conn.close()
    return [_normalize_item(row) or {} for row in rows]
