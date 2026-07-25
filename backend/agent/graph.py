import sqlite3

import structlog
from langchain_core.messages import SystemMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.prebuilt import create_react_agent

from backend.agent.profile import build_profile_context, is_onboarding
from backend.agent.prompts import NO_ONBOARDING, ONBOARDING_PROMPT, SYSTEM_PROMPT
from backend.agent.tools import ALL_TOOLS
from backend.config import CHECKPOINT_DB_PATH, LLM_PROVIDER
from backend.llm import (
    get_chat_model,
    get_model_label,
    sanitize_messages_for_remote_llm,
    should_redact_identity,
)

log = structlog.get_logger()

_graph = None
_checkpointer = None


def _build_prompt(state: dict) -> list:
    """Build the system prompt with live profile context injected."""
    # Extract current message for semantic retrieval
    messages = state.get("messages", [])
    current_msg = ""
    if messages:
        last = messages[-1]
        current_msg = last.content if hasattr(last, "content") else str(last)

    profile_context = build_profile_context(
        current_message=current_msg,
        redact_identity=should_redact_identity(),
    )
    onboarding_context = ONBOARDING_PROMPT if is_onboarding() else NO_ONBOARDING

    system_content = SYSTEM_PROMPT.format(
        profile_context=profile_context,
        onboarding_context=onboarding_context,
    )

    return [SystemMessage(content=system_content)] + sanitize_messages_for_remote_llm(
        state["messages"]
    )


def get_graph():
    """Get or create the LangGraph ReAct agent."""
    global _graph, _checkpointer

    if _graph is not None:
        return _graph

    log.info(
        "agent_init",
        provider=LLM_PROVIDER,
        model=get_model_label(),
        tools=len(ALL_TOOLS),
    )

    model = get_chat_model(
        temperature=0.7,
        context_window=8192,
        purpose="agent",
    )

    conn = sqlite3.connect(str(CHECKPOINT_DB_PATH), check_same_thread=False)
    _checkpointer = SqliteSaver(conn)

    _graph = create_react_agent(
        model,
        ALL_TOOLS,
        checkpointer=_checkpointer,
        prompt=_build_prompt,
    )

    log.info("agent_ready")
    return _graph
