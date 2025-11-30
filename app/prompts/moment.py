"""Moment step prompt templates.

The Moment step captures narrative tension, stakes, and
dramatic arc of the scene.

Examples:
    >>> from app.prompts.moment import get_prompt
    >>> prompt = get_prompt("signing of the declaration", "July 4, 1776")
"""

SYSTEM_PROMPT = """You are a narrative designer for TIMEPOINT, an AI system that
generates immersive visual scenes from temporal moments.

Your task is to capture the dramatic narrative of a moment:
- What's happening (plot)
- What's at stake (tension)
- The emotional arc
- Why this moment matters

GUIDELINES:
1. Identify the central dramatic question
2. Describe what happened just before and what happens after
3. Capture the stakes and consequences
4. Note any dramatic irony (what we know that characters don't)
5. Rate the tension arc (rising, falling, climactic, resolved)

EXAMPLES:
- Signing of Declaration: "Climactic moment of defiance, risking lives for liberty"
- Rome 50 BCE: "Tension rising as Caesar consolidates power"
- Battle of Thermopylae: "Last stand, sacrifice for Greece's survival"

Respond with a JSON object matching the MomentData schema."""

USER_PROMPT_TEMPLATE = """Capture the narrative moment for this scene:

Query: "{query}"

Context:
- Year: {year}
- Era: {era}
- Location: {location}
- Scene: {setting}
- Atmosphere: {atmosphere}

Characters Present: {characters}

Determine:
1. What's happening in this moment (plot summary)
2. What happened just before / what happens next
3. What's at stake
4. The tension arc (rising, falling, climactic, resolved)
5. Key emotional beats
6. Any dramatic irony
7. Historical significance

Respond with valid JSON matching this schema:
{{
  "plot_summary": "what's happening",
  "before_context": "what just happened",
  "after_context": "what happens next",
  "stakes": "what's at risk",
  "consequences": "potential consequences",
  "tension_arc": "rising|falling|climactic|resolved",
  "emotional_beats": ["list", "of", "emotions"],
  "conflict_type": "internal|interpersonal|societal|external",
  "central_question": "the dramatic question",
  "dramatic_irony": "what viewer knows" | null,
  "historical_significance": "why it matters"
}}"""


def get_prompt(
    query: str,
    year: int,
    era: str | None,
    location: str,
    setting: str,
    atmosphere: str,
    characters: list[str] | None = None,
) -> str:
    """Get the user prompt for moment generation.

    Args:
        query: The cleaned query
        year: Year of the scene
        era: Historical era
        location: Location
        setting: Scene setting
        atmosphere: Scene atmosphere
        characters: Character names

    Returns:
        Formatted user prompt
    """
    year_str = f"{abs(year)} BCE" if year < 0 else str(year)
    char_str = ", ".join(characters) if characters else "Various characters"

    return USER_PROMPT_TEMPLATE.format(
        query=query,
        year=year_str,
        era=era or "Unknown",
        location=location,
        setting=setting,
        atmosphere=atmosphere,
        characters=char_str,
    )


def get_system_prompt() -> str:
    """Get the system prompt for the moment step."""
    return SYSTEM_PROMPT
