"""Character Identification prompt templates.

Phase 1 of two-phase character generation - fast identification of
who should be in the scene before parallel bio generation.

Examples:
    >>> from app.prompts.character_identification import get_prompt
    >>> prompt = get_prompt(query, year, era, location, setting, ...)
"""

SYSTEM_PROMPT = """You are a historical character planner for TIMEPOINT, an AI system that
generates immersive visual scenes from temporal moments.

Your task is to QUICKLY IDENTIFY which characters should appear in the scene.
This is Phase 1 - you are NOT writing full character descriptions yet.

For each character provide ONLY:
- Name (or descriptive identifier for unnamed characters)
- Role: primary (1-2), secondary (2-3), or background (2-4)
- One-sentence description of who they are
- Whether they speak in the scene (for dialog generation)
- Key relationships to other characters in the scene

GUIDELINES:
1. Maximum 8 characters total for visual clarity
2. For historical events, identify known figures who would be present
3. Include a mix of roles for visual depth
4. Mark 2-4 characters as speaking for dialog generation
5. Note relationships that will inform character interactions

IMPORTANT: Keep descriptions BRIEF - detailed bios come in Phase 2.

Respond with a JSON object matching the CharacterIdentification schema."""

USER_PROMPT_TEMPLATE = """Identify characters for this temporal scene:

Query: "{query}"

Timeline:
- Year: {year} {era}
- Location: {location}

Scene Context:
- Setting: {setting}
- Atmosphere: {atmosphere}
- Tension: {tension_level}

Historical figures mentioned: {detected_figures}

QUICKLY identify up to 8 characters:
- 1-2 PRIMARY (main focus)
- 2-3 SECONDARY (supporting)
- 2-4 BACKGROUND (atmosphere)

For each character provide ONLY:
1. Name
2. Role (primary/secondary/background)
3. One-sentence description
4. speaks_in_scene (true/false) - mark 2-4 characters
5. Key relationships (list of other character names)

Respond with valid JSON:
{{
  "characters": [
    {{
      "name": "character name",
      "role": "primary|secondary|background",
      "brief_description": "one sentence about who they are",
      "speaks_in_scene": boolean,
      "key_relationships": ["name1", "name2"]
    }}
  ],
  "focal_character": "name of primary focal character",
  "group_dynamics": "brief description of character relationships",
  "historical_accuracy_note": "optional note about accuracy"
}}

Keep it FAST - detailed descriptions come next."""


def get_prompt(
    query: str,
    year: int,
    era: str | None,
    location: str,
    setting: str,
    atmosphere: str,
    tension_level: str,
    detected_figures: list[str] | None = None,
) -> str:
    """Get the user prompt for character identification.

    Args:
        query: The cleaned query
        year: The year
        era: Historical era
        location: Geographic location
        setting: Scene setting description
        atmosphere: Scene atmosphere
        tension_level: Dramatic tension level
        detected_figures: Historical figures from judge

    Returns:
        Formatted user prompt
    """
    year_str = f"{abs(year)} BCE" if year < 0 else str(year)
    figures_str = ", ".join(detected_figures) if detected_figures else "None detected"

    return USER_PROMPT_TEMPLATE.format(
        query=query,
        year=year_str,
        era=era or "Unknown",
        location=location,
        setting=setting,
        atmosphere=atmosphere,
        tension_level=tension_level,
        detected_figures=figures_str,
    )


def get_system_prompt() -> str:
    """Get the system prompt for character identification."""
    return SYSTEM_PROMPT
