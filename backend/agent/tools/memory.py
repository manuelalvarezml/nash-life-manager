from langchain_core.tools import tool
from backend.db.schema import insert_memory


@tool
def log_memory(
    topic: str,
    content: str,
    life_period: str = "unspecified",
) -> str:
    """Log a memory, story, or anecdote from Manuel's past. Use when he shares personal history, \
    childhood experiences, family stories, relationship milestones, or formative events.

    Args:
        topic: Short topic label (e.g. 'relationship with father', 'first job', 'school bullying')
        content: The full memory content as Manuel described it
        life_period: One of 'childhood', 'adolescence', 'youth', 'present', 'unspecified'
    """
    memory_id = insert_memory(
        topic=topic,
        raw_transcript=content,
        life_period=life_period,
    )
    return f"Memory #{memory_id} saved (topic='{topic}', period={life_period})"
