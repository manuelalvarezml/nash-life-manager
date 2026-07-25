from backend.agent.tools.diary import log_diary_entry, get_recent_entries
from backend.agent.tools.memory import log_memory
from backend.agent.tools.profile_tools import log_profile_fact

ALL_TOOLS = [
    log_diary_entry,
    get_recent_entries,
    log_memory,
    log_profile_fact,
]
