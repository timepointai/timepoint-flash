"""Character Bio prompt templates.

Phase 2 of two-phase character generation - detailed bio for a single
character, run in parallel for all characters.

Examples:
    >>> from app.prompts.character_bio import get_prompt
    >>> prompt = get_prompt(stub, cast_context, year, era, location, ...)
"""

from app.prompts.sanitize import sanitize_prompt_input

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
- voice_contrast: How this character sounds DIFFERENT from the other speakers

VOICE DIFFERENTIATION (critical for speaking characters):
Social class and education MUST determine speech patterns:
- Elite/noble: Complex sentence structure, subordinate clauses, abstract concepts
- Educated commoner: Clear declarative sentences, practical metaphors, moderate vocabulary
- Common laborer: Short sentences, concrete language, trade-specific terms
- Servant/slave: Fragments, deferential phrasing, indirect speech, hedging
- Child: Simple vocabulary, questions, incomplete thoughts

Each speaking character MUST sound recognizably different from every other speaker.
If two characters would sound similar, differentiate by: sentence length, vocabulary
level, use of questions vs statements, directness vs indirectness, or verbal tics.

GUIDELINES:
1. For historical figures, use accurate physical descriptions when known
2. Include period-appropriate clothing with specific details
3. Expressions should reflect the dramatic moment
4. Reference their relationships with other characters in the scene
5. For known historical figures, capture their documented personality
6. Ensure consistency with the full cast dynamics
7. Use period-authentic deity names and cultural references (Roman = Jupiter/Pluto/Dis Pater,
   NOT Greek equivalents like Zeus/Hades unless the setting is Greek)
8. Avoid modern English idioms in voice_notes — flag any that slip through

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
  "voice_notes": "speech patterns, verbal quirks — NO modern idioms" | null,
  "emotional_state": "current emotional state" | null
}}

IMPORTANT:
- Ensure this character's portrayal reflects their relationships
  with other characters in the scene, especially: {key_relationships}
- For speaking characters: their voice MUST be distinguishable from all other speakers.
  Vary sentence length, vocabulary level, directness, and verbal tics by social class.
- Use culturally correct references (Roman setting = Roman deities/idioms, NOT Greek)
- Do NOT use modern English idioms (e.g., "six feet under", "beat around the bush")"""


def format_grounded_context(profile: dict) -> str:
    """Format grounded profile data for injection into bio prompt.

    Converts a raw grounding profile dict (as stored on PipelineState or
    passed from CharacterBioInput) into a concise text block suitable for
    prepending to the character bio prompt.

    Args:
        profile: Grounding profile dict (may be a GroundingProfile.model_dump()
                 or a plain dict with compatible keys).

    Returns:
        Formatted grounded context string, or empty string if profile is empty.
    """
    if not profile:
        return ""

    lines = ["GROUNDED ENTITY DATA (factual — use to anchor physical details and biography):"]

    biography = profile.get("biography_summary", "").strip()
    if biography:
        lines.append(f"Biography: {sanitize_prompt_input(biography)}")

    appearance = profile.get("appearance_description", "").strip()
    if appearance:
        lines.append(f"Appearance: {sanitize_prompt_input(appearance)}")

    affiliations = profile.get("known_affiliations", [])
    if affiliations:
        safe_affiliations = [sanitize_prompt_input(a) for a in affiliations if a]
        if safe_affiliations:
            lines.append(f"Affiliations: {', '.join(safe_affiliations)}")

    citations = profile.get("source_citations", [])
    if citations:
        lines.append(f"Sources: {len(citations)} reference(s) used for grounding")

    confidence = profile.get("confidence")
    if confidence is not None:
        lines.append(f"Grounding confidence: {confidence:.2f}")

    lines.append("Use this grounded data to ensure factual accuracy in the bio.")
    return "\n".join(lines)


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
    grounded_profile: dict | None = None,
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
        grounded_profile: Optional grounded entity profile dict (optional)

    Returns:
        Formatted user prompt, with grounded context prepended when available
    """
    year_str = f"{abs(year)} BCE" if year < 0 else str(year)
    relations_str = (
        ", ".join(sanitize_prompt_input(r) for r in key_relationships)
        if key_relationships
        else "None"
    )

    # Format relationship section (only if graph data provided)
    relationship_section = ""
    if relationship_context:
        relationship_section = f"""RELATIONSHIP GRAPH (from scene analysis):
{sanitize_prompt_input(relationship_context)}

Use these relationship dynamics to inform the character's expression, pose, and emotional state."""

    base_prompt = USER_PROMPT_TEMPLATE.format(
        character_name=sanitize_prompt_input(character_name),
        character_role=sanitize_prompt_input(character_role),
        character_brief=sanitize_prompt_input(character_brief),
        speaks_in_scene="Yes" if speaks_in_scene else "No",
        speaks_in_scene_json="true" if speaks_in_scene else "false",
        key_relationships=relations_str,
        cast_context=sanitize_prompt_input(cast_context),
        relationship_section=relationship_section,
        query=sanitize_prompt_input(query),
        year=year_str,
        era=sanitize_prompt_input(era) if era else "Unknown",
        location=sanitize_prompt_input(location),
        setting=sanitize_prompt_input(setting),
        atmosphere=sanitize_prompt_input(atmosphere),
        tension_level=sanitize_prompt_input(tension_level),
    )

    # Prepend grounded context when available
    if grounded_profile:
        grounded_block = format_grounded_context(grounded_profile)
        if grounded_block:
            return grounded_block + "\n\n" + base_prompt

    return base_prompt


def get_system_prompt() -> str:
    """Get the system prompt for character bio generation."""
    return SYSTEM_PROMPT
