"""
Judge/Clean/Clarify agent using Llama 4 Scout.

This agent validates user input for:
- Appropriateness (time travel query)
- Clarity (can other agents understand it)
- Security (NSFW content, prompt injection)

Returns cleaned/clarified prompt or rejection.
"""
from pydantic import BaseModel, Field
from app.services.google_ai import call_llm
from app.config import settings
import instructor


class JudgmentResult(BaseModel):
    """Result of judge agent validation."""
    is_valid: bool = Field(..., description="Whether the query is valid for time travel")
    cleaned_query: str = Field(..., description="Cleaned and clarified version of the query")
    reason: str | None = Field(None, description="Reason for rejection if invalid")
    era: str = Field(..., description="Time period (e.g., 'Ancient Rome', '1960s')")
    category: str = Field(..., description="Type of scene (historical event, daily life, etc.)")


async def judge_query(user_query: str) -> JudgmentResult:
    """
    Validate and clean user's time travel query.

    Args:
        user_query: Raw user input

    Returns:
        JudgmentResult with validation status and cleaned query
    """
    system_prompt = """You are a judge agent for a time travel application.

Your role:
1. Validate if the input is a valid time travel query (point in time, historical event, era)
2. Clean and clarify the query for other agents to understand
3. Reject inappropriate content (NSFW, harmful, nonsensical)
4. Extract the era/time period and categorize the scene

Valid examples:
- "signing of the constitutional convention"
- "medieval marketplace in 1250"
- "1960s diner"
- "ancient Roman gladiator fight"

Invalid examples:
- Nonsensical text
- NSFW content
- Modern events within last 5 years
- Requests for harmful content

Return structured validation result."""

    user_prompt = f"Validate and clean this time travel query: {user_query}"

    # Call LLM with structured output using instructor
    result = await call_llm(
        model=settings.JUDGE_MODEL,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        response_model=JudgmentResult,
        temperature=0.1,  # Low temperature for consistency
        max_tokens=4000  # Moderate limit for validation
    )

    return result
