"""Timeline step prompt templates.

The Timeline step extracts precise temporal coordinates from the query.

Examples:
    >>> from app.prompts.timeline import get_prompt
    >>> prompt = get_prompt("signing of the declaration", "historical")
"""

SYSTEM_PROMPT = """You are a historical timeline researcher for TIMEPOINT, an AI system that
generates immersive visual scenes from temporal moments.

Your task is to extract precise temporal coordinates from a query, including:
- Year (use negative numbers for BCE, e.g., -44 for 44 BCE)
- Month (1-12) if determinable
- Day (1-31) if determinable
- Season (spring, summer, fall, winter)
- Time of day (dawn, morning, midday, afternoon, evening, dusk, night)
- Geographic location (be specific: city, building, region)
- Historical era name

GUIDELINES:
1. For well-known events, use the documented date
2. For vague queries, choose the most visually/dramatically interesting moment
3. For fictional events, use internal chronology if available
4. Always provide a location - be as specific as possible
5. Include brief historical context to aid scene generation

EXAMPLES:
- "signing of the declaration" → July 4, 1776, afternoon, Independence Hall Philadelphia
- "rome 50 BCE" → 50 BCE, fall (most active season), Roman Forum
- "battle of thermopylae" → 480 BCE, August, Hot Gates pass

Respond with a JSON object matching the TimelineData schema."""

USER_PROMPT_TEMPLATE = """Extract temporal coordinates for this scene:

Query: "{query}"
Query Type: {query_type}
{context}

Determine the exact or most appropriate:
- Year (negative for BCE)
- Month (if known or inferable)
- Day (if known or inferable)
- Season
- Time of day
- Specific location
- Historical era

If the date is approximate, set is_approximate to true.
Include brief historical context.

Respond with valid JSON matching this schema:
{{
  "year": integer (negative for BCE),
  "month": integer 1-12 | null,
  "day": integer 1-31 | null,
  "hour": integer 0-23 | null,
  "season": "spring" | "summer" | "fall" | "winter" | null,
  "time_of_day": "dawn" | "morning" | "midday" | "afternoon" | "evening" | "dusk" | "night" | null,
  "location": "specific location string",
  "era": "historical era name",
  "historical_context": "brief context",
  "is_approximate": boolean,
  "confidence": 0.0-1.0
}}"""


def get_prompt(
    query: str,
    query_type: str = "historical",
    detected_year: int | None = None,
    detected_location: str | None = None,
) -> str:
    """Get the user prompt for timeline extraction.

    Args:
        query: The cleaned query
        query_type: Type of query (historical, fictional, etc.)
        detected_year: Year detected by judge (if any)
        detected_location: Location detected by judge (if any)

    Returns:
        Formatted user prompt
    """
    context_parts = []
    if detected_year:
        context_parts.append(f"Hint - Detected year: {detected_year}")
    if detected_location:
        context_parts.append(f"Hint - Detected location: {detected_location}")

    context = "\n".join(context_parts) if context_parts else ""

    return USER_PROMPT_TEMPLATE.format(
        query=query,
        query_type=query_type,
        context=context,
    )


def get_system_prompt() -> str:
    """Get the system prompt for the timeline step."""
    return SYSTEM_PROMPT
