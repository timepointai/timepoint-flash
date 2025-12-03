"""Character Bio prompt templates.

Phase 2 of two-phase character generation - detailed bio for a single
character, run in parallel for all characters.

Examples:
    >>> from app.prompts.character_bio import get_prompt
    >>> prompt = get_prompt(stub, cast_context, year, era, location, ...)
"""

SYSTEM_PROMPT = """You are a historical character designer for TIMEPOINT, an AI system that
generates immersive visual scenes from temporal moments.

Your task is to create a DETAILED character bio for ONE specific character.
You will receive information about ALL characters in the scene to ensure
your character's relationships and interactions are accurately portrayed.

For this character provide:
- Physical description (age, build, features)
- Period-appropriate clothing with specific details
- Facial expression reflecting the moment
- Body pose (dynamic and natural)
- Current action
- Position in scene

FOR SPEAKING CHARACTERS, also provide:
- Personality: Core traits (e.g., "witty, diplomatic, cautious")
- Speaking style: How they talk (e.g., "formal, eloquent, uses metaphors")
- Voice notes: Speech patterns, accent hints, verbal quirks
- Emotional state: Their current mood in this scene

GUIDELINES:
1. For historical figures, use accurate physical descriptions when known
2. Include period-appropriate clothing with specific details
3. Expressions should reflect the dramatic moment
4. Reference their relationships with other characters in the scene
5. For known historical figures, capture their documented personality
6. Ensure consistency with the full cast dynamics

Respond with a JSON object matching the Character schema."""

USER_PROMPT_TEMPLATE = """Generate a detailed bio for this character:

TARGET CHARACTER:
- Name: {character_name}
- Role: {character_role}
- Description: {character_brief}
- Speaks in scene: {speaks_in_scene}
- Key relationships: {key_relationships}

{cast_context}

{relationship_section}

SCENE CONTEXT:
- Query: "{query}"
- Year: {year} {era}
- Location: {location}
- Setting: {setting}
- Atmosphere: {atmosphere}
- Tension: {tension_level}

Generate a complete bio for {character_name}:

Respond with valid JSON:
{{
  "name": "{character_name}",
  "role": "{character_role}",
  "description": "detailed physical description",
  "clothing": "period-specific clothing details",
  "expression": "facial expression",
  "pose": "body pose",
  "action": "current action",
  "position_in_scene": "where in the scene",
  "age_description": "approximate age",
  "historical_note": "historical context if known figure" | null,
  "speaks_in_scene": {speaks_in_scene_json},
  "personality": "core traits (required if speaks)" | null,
  "speaking_style": "how they talk (required if speaks)" | null,
  "voice_notes": "speech patterns, verbal quirks" | null,
  "emotional_state": "current emotional state" | null
}}

IMPORTANT: Ensure this character's portrayal reflects their relationships
with other characters in the scene, especially: {key_relationships}"""


def get_prompt(
    character_name: str,
    character_role: str,
    character_brief: str,
    speaks_in_scene: bool,
    key_relationships: list[str],
    cast_context: str,
    query: str,
    year: int,
    era: str | None,
    location: str,
    setting: str,
    atmosphere: str,
    tension_level: str,
    relationship_context: str = "",
) -> str:
    """Get the user prompt for character bio generation.

    Args:
        character_name: Name of the character
        character_role: Role (primary/secondary/background)
        character_brief: One-sentence description
        speaks_in_scene: Whether character speaks
        key_relationships: List of related character names
        cast_context: Full cast context from CharacterIdentification
        query: The original query
        year: The year
        era: Historical era
        location: Geographic location
        setting: Scene setting
        atmosphere: Scene atmosphere
        tension_level: Dramatic tension level
        relationship_context: Detailed relationship info from graph (optional)

    Returns:
        Formatted user prompt
    """
    year_str = f"{abs(year)} BCE" if year < 0 else str(year)
    relations_str = ", ".join(key_relationships) if key_relationships else "None"

    # Format relationship section (only if graph data provided)
    relationship_section = ""
    if relationship_context:
        relationship_section = f"""RELATIONSHIP GRAPH (from scene analysis):
{relationship_context}

Use these relationship dynamics to inform the character's expression, pose, and emotional state."""

    return USER_PROMPT_TEMPLATE.format(
        character_name=character_name,
        character_role=character_role,
        character_brief=character_brief,
        speaks_in_scene="Yes" if speaks_in_scene else "No",
        speaks_in_scene_json="true" if speaks_in_scene else "false",
        key_relationships=relations_str,
        cast_context=cast_context,
        relationship_section=relationship_section,
        query=query,
        year=year_str,
        era=era or "Unknown",
        location=location,
        setting=setting,
        atmosphere=atmosphere,
        tension_level=tension_level,
    )


def get_system_prompt() -> str:
    """Get the system prompt for character bio generation."""
    return SYSTEM_PROMPT
