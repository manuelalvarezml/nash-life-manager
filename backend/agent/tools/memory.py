from langchain_core.tools import tool
import json

from backend.db.schema import get_memories, insert_structured_memory


@tool
def log_memory(
    topic: str,
    content: str,
    life_period: str = "unspecified",
    age: int | None = None,
    year: int | None = None,
    place: str | None = None,
) -> str:
    """Log a memory, story, or anecdote from the user's past. Use when they share personal history, \
    childhood experiences, family stories, relationship milestones, or formative events.

    Args:
        topic: Short topic label (e.g. 'relationship with father', 'first job', 'school bullying')
        content: The full memory content as the user described it
        life_period: One of 'childhood', 'adolescence', 'youth', 'present', 'unspecified'
    """
    memory = insert_structured_memory(
        {
            "title": topic,
            "raw_transcript": content,
            "life_period": life_period,
            "age_start": age,
            "age_end": age,
            "occurred_year_start": year,
            "occurred_year_end": year,
            "place_name": place,
            "confidence": 1.0 if year is not None else 0.7,
        }
    )
    return f"Memory #{memory['id']} saved (topic='{topic}', period={life_period})"


@tool
def search_memories(query: str, limit: int = 10) -> str:
    """Search the autobiographical memory archive by topic, place, person, or text."""
    memories = get_memories(limit=max(1, min(limit, 30)), search=query)
    compact = [
        {
            "id": memory.get("id"),
            "title": memory.get("title") or memory.get("topic"),
            "years": [memory.get("occurred_year_start"), memory.get("occurred_year_end")],
            "ages": [memory.get("age_start"), memory.get("age_end")],
            "place": memory.get("place_name"),
            "people": memory.get("people"),
            "themes": memory.get("themes"),
            "content": memory.get("raw_transcript"),
        }
        for memory in memories
    ]
    return json.dumps(compact, ensure_ascii=False)
