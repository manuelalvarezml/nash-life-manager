from backend.agent.tools.diary import log_diary_entry, get_recent_entries
from backend.agent.tools.memory import log_memory, search_memories
from backend.agent.tools.profile_tools import log_profile_fact
from backend.agent.tools.calendar import apply_schedule_instruction, get_upcoming_schedule

ALL_TOOLS = [
    log_diary_entry,
    get_recent_entries,
    log_memory,
    search_memories,
    log_profile_fact,
    apply_schedule_instruction,
    get_upcoming_schedule,
]
