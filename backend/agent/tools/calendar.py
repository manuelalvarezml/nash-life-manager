import json

from langchain_core.tools import tool

from backend.calendar_engine import process_schedule_input
from backend.db.calendar import get_upcoming_calendar_items


@tool
def apply_schedule_instruction(instruction: str) -> str:
    """Apply an explicit calendar instruction from the user using Nash's canonical scheduler.

    Use only when the user clearly asks to create, move, complete, cancel, or rearrange
    calendar commitments. Do not schedule vague wishes, reflections, or inferred needs.
    """
    result = process_schedule_input(instruction, input_mode="text")
    safe_result = {
        "status": result.get("status"),
        "message": result.get("message"),
        "item": result.get("item"),
        "series": result.get("series"),
        "candidates": result.get("candidates"),
    }
    return json.dumps(safe_result, ensure_ascii=False)


@tool
def get_upcoming_schedule(days: int = 7) -> str:
    """Read accepted upcoming calendar commitments for the next 1 to 30 days."""
    items = get_upcoming_calendar_items(days=max(1, min(days, 30)), limit=50)
    compact = [
        {
            "id": item.get("id"),
            "title": item.get("title"),
            "start_at": item.get("start_at"),
            "end_at": item.get("end_at"),
            "source": item.get("source_kind"),
            "flexibility": item.get("flexibility"),
            "status": item.get("status"),
        }
        for item in items
    ]
    return json.dumps(compact, ensure_ascii=False)
