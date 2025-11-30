"""Dialog step prompt templates.

The Dialog step generates up to 7 lines of period-appropriate dialog.

Examples:
    >>> from app.prompts.dialog import get_prompt
    >>> prompt = get_prompt(query, timeline_data, characters)
"""

SYSTEM_PROMPT = """You are a historical dialog writer for TIMEPOINT, an AI system that
generates immersive visual scenes from temporal moments.

Your task is to write up to 7 lines of dialog that capture this moment:
- Use period-appropriate language and speech patterns
- Each line should advance the dramatic moment
- Include tone and delivery notes
- Note any physical actions while speaking

GUIDELINES:
1. Use language authentic to the time period and location
2. Important figures should sound distinctive
3. Dialog should capture the dramatic tension
4. Include non-verbal cues (whispers, shouts, etc.)
5. Background characters may have brief lines
6. Consider what would actually be said in this moment

EXAMPLES of period language:
- 18th century formal: "Gentlemen, I submit that we must act with dispatch."
- Medieval: "By my faith, the hour grows late."
- Ancient Rome: "The Senate awaits your words, consul."

IMPORTANT: Maximum 7 lines for visual coherence.

Respond with a JSON object matching the DialogData schema."""

USER_PROMPT_TEMPLATE = """Write dialog for this temporal moment:

Query: "{query}"

Timeline:
- Year: {year} {era}
- Location: {location}

Scene:
- Setting: {setting}
- Atmosphere: {atmosphere}
- Tension: {tension_level}

Speaking Characters:
{character_list}

Write up to 7 lines of period-appropriate dialog:
- Use authentic language for the time period
- Capture the dramatic moment
- Include tone and action notes
- Make each line meaningful

Respond with valid JSON matching this schema:
{{
  "lines": [
    {{
      "speaker": "character name",
      "text": "the dialog line",
      "tone": "formal|urgent|whispered|casual|etc" | null,
      "is_whispered": boolean,
      "action": "physical action while speaking" | null,
      "direction": "stage direction" | null,
      "response_to": "character being addressed" | null
    }}
  ],
  "scene_context": "context for this conversation",
  "language_style": "description of period language style",
  "historical_accuracy_note": "note about dialog accuracy" | null
}}"""


def get_prompt(
    query: str,
    year: int,
    era: str | None,
    location: str,
    setting: str,
    atmosphere: str,
    tension_level: str,
    speaking_characters: list[str],
) -> str:
    """Get the user prompt for dialog generation.

    Args:
        query: The cleaned query
        year: The year
        era: Historical era
        location: Geographic location
        setting: Scene setting
        atmosphere: Scene atmosphere
        tension_level: Dramatic tension
        speaking_characters: Names of characters who speak

    Returns:
        Formatted user prompt
    """
    year_str = f"{abs(year)} BCE" if year < 0 else str(year)
    char_list = "\n".join(f"- {name}" for name in speaking_characters)

    return USER_PROMPT_TEMPLATE.format(
        query=query,
        year=year_str,
        era=era or "Unknown",
        location=location,
        setting=setting,
        atmosphere=atmosphere,
        tension_level=tension_level,
        character_list=char_list,
    )


def get_system_prompt() -> str:
    """Get the system prompt for the dialog step."""
    return SYSTEM_PROMPT
