from langchain_core.tools import tool
from backend.db.schema import insert_profile_fact


@tool
def log_profile_fact(
    domain: str,
    statement: str,
    fact_type: str = "declared",
) -> str:
    """Log a fact about Manuel's personality, identity, or behavioral patterns. Use when Manuel \
    makes a direct statement about who he is, what he struggles with, or how he tends to behave.

    Args:
        domain: One of 'identity', 'patterns', 'sabotage', 'strengths', 'relationships', 'narrative', 'goals'
        statement: The specific fact or self-description (in Manuel's words when possible)
        fact_type: 'declared' for things Manuel says directly, 'behavioral' for observed patterns, 'inferred' for deductions
    """
    fact_id = insert_profile_fact(
        domain=domain,
        statement=statement,
        fact_type=fact_type,
        source_type="conversation",
    )
    return f"Profile fact #{fact_id} saved (domain='{domain}', type={fact_type})"
