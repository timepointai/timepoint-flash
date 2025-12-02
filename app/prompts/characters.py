"""Characters step prompt templates.

The Characters step generates up to 8 characters for the scene.

Examples:
    >>> from app.prompts.characters import get_prompt
    >>> prompt = get_prompt(query, timeline_data, scene_data)
"""

SYSTEM_PROMPT = """You are a historical character designer for TIMEPOINT, an AI system that
generates immersive visual scenes from temporal moments.

Your task is to create up to 8 characters for the scene:
- 1-2 PRIMARY characters: Central figures, detailed descriptions
- 2-3 SECONDARY characters: Important supporting figures
- 2-4 BACKGROUND characters: Atmosphere and context

For each character provide:
- Name (or descriptive identifier for unnamed)
- Role (primary/secondary/background)
- Physical description (age, build, features)
- Period-appropriate clothing
- Facial expression
- Body pose
- Current action
- Position in scene

FOR SPEAKING CHARACTERS (speaks_in_scene=true), also provide:
- Personality: Core traits (e.g., "witty, diplomatic, cautious")
- Speaking style: How they talk (e.g., "formal, eloquent, uses biblical references")
- Voice notes: Speech patterns, accent hints, verbal quirks
- Emotional state: Their current mood in this scene

GUIDELINES:
1. For historical figures, use accurate physical descriptions when known
2. Include period-appropriate clothing with specific details
3. Expressions should reflect the dramatic moment
4. Poses should be dynamic and natural
5. Background characters add depth but shouldn't distract
6. Note which characters speak in the scene
7. For known historical figures, capture their documented personality and speaking style
8. Personality informs how they express ideas; speaking style informs word choice

IMPORTANT: Maximum 8 characters for visual clarity.

Respond with a JSON object matching the CharacterData schema."""

USER_PROMPT_TEMPLATE = """Design characters for this temporal scene:

Query: "{query}"

Timeline:
- Year: {year} {era}
- Location: {location}

Scene Context:
- Setting: {setting}
- Atmosphere: {atmosphere}
- Tension: {tension_level}

Historical figures mentioned: {detected_figures}

Create up to 8 characters:
- 1-2 PRIMARY characters (main focus)
- 2-3 SECONDARY characters (supporting)
- 2-4 BACKGROUND characters (atmosphere)

For each character include:
- Name and role
- Physical description
- Period clothing details
- Expression and pose
- Current action
- Position in scene

Respond with valid JSON matching this schema:
{{
  "characters": [
    {{
      "name": "character name or description",
      "role": "primary|secondary|background",
      "description": "physical description",
      "clothing": "period clothing details",
      "expression": "facial expression",
      "pose": "body pose",
      "action": "current action",
      "position_in_scene": "where in the scene",
      "age_description": "approximate age",
      "historical_note": "historical context if known figure" | null,
      "speaks_in_scene": boolean,
      "personality": "core traits (for speaking characters)" | null,
      "speaking_style": "how they talk (for speaking characters)" | null,
      "voice_notes": "speech patterns, verbal quirks" | null,
      "emotional_state": "current emotional state in scene" | null
    }}
  ],
  "focal_character": "name of primary focal character",
  "group_dynamics": "description of character relationships",
  "historical_accuracy_note": "note about accuracy" | null
}}

NOTE: For characters with speaks_in_scene=true, personality and speaking_style
are REQUIRED for authentic dialog generation."""


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
    """Get the user prompt for character generation.

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
    """Get the system prompt for the characters step."""
    return SYSTEM_PROMPT
