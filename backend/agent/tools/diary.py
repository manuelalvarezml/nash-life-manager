from langchain_core.tools import tool
from backend.db.schema import insert_diary_entry, get_recent_diary_entries


@tool
def log_diary_entry(
    entry_type: str,
    content: str,
    energy_level: int = 5,
    summary: str = "",
    domain_tags: str = "[]",
) -> str:
    """Log a diary entry when Manuel shares how he's feeling, what happened today, or reflects on his day.

    Args:
        entry_type: One of 'morning', 'night', or 'spontaneous'
        content: The full content of what Manuel shared
        energy_level: Energy level from 1 (exhausted) to 10 (full energy), estimate from what he said
        summary: A brief 1-sentence summary of the entry
        domain_tags: JSON array of relevant domains like '["work", "relationships", "health"]'
    """
    entry_id = insert_diary_entry(
        entry_type=entry_type,
        raw_transcript=content,
        summary=summary,
        domain_tags=domain_tags,
        energy_level=energy_level,
    )
    return f"Diary entry #{entry_id} saved ({entry_type}, energy={energy_level})"


@tool
def get_recent_entries(n: int = 5) -> str:
    """Retrieve the most recent diary entries to understand Manuel's recent state.

    Args:
        n: Number of recent entries to retrieve (default 5)
    """
    entries = get_recent_diary_entries(n)
    if not entries:
        return "No diary entries found yet."

    parts = []
    for e in entries:
        parts.append(
            f"[{e['timestamp']}] ({e['entry_type']}, energy={e['energy_level']}): {e['raw_transcript'][:300]}"
        )
    return "\n---\n".join(parts)
