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
- Role: primary (1-2), secondary (2-3), or background (0-2)
- One-sentence description of who they are
- Whether they speak in the scene (for dialog generation)
- Key relationships to other characters in the scene

NAMING RULES:
1. For known historical figures, use their actual name
2. For fictional/unnamed characters, use GENERIC period-appropriate identifiers
   (e.g., "Baker", "Slave Boy", "Guard Captain") — NOT literary or famous names
3. Do NOT use names from well-known literary works unless historically documented
   (e.g., "Fortunata" is from Petronius's Satyricon — use "Baker's Wife" instead)
4. Roman names should follow praenomen-nomen-cognomen convention if named at all

CASTING RULES:
1. Maximum 6 characters total (fewer is better for visual + dialog quality)
2. Every character MUST serve the scene — no decorative extras
3. Background characters must have a visible action or reaction (not just "standing there")
4. Only include characters who INTERACT with the moment — if they don't react to or
   participate in the central event, cut them
5. Mark 2-4 characters as speaking — every speaking character must have a DISTINCT
   social register (class, education, authority level) that differentiates their voice
6. Silent characters need justification: what are they DOING that adds to the scene?

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

Identify up to 6 characters (fewer is better):
- 1-2 PRIMARY (main focus, always speak)
- 1-3 SECONDARY (supporting, may speak)
- 0-2 BACKGROUND (only if they have a visible action/reaction)

RULES:
- Every character must DO something in the scene — no passive observers
- Silent characters must have a described physical reaction to the moment
- Use historically authentic names or generic identifiers, NOT literary references
- Each speaking character needs a different social register (noble vs common,
  educated vs uneducated, authority vs subordinate)

For each character provide ONLY:
1. Name (or generic identifier like "Baker", "Guard")
2. Role (primary/secondary/background)
3. One-sentence description
4. speaks_in_scene (true/false) - mark 2-4 characters
5. Key relationships (list of other character names)
6. social_register: one of "elite", "educated", "common", "servant/slave", "child"
   (MUST be different for each speaking character)

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
    verified_participants: str = "",
    grounding_notes: str = "",
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
        verified_participants: Verified participants from grounding
        grounding_notes: Historical setting details from grounding

    Returns:
        Formatted user prompt
    """
    year_str = f"{abs(year)} BCE" if year < 0 else str(year)
    figures_str = ", ".join(detected_figures) if detected_figures else "None detected"

    prompt = USER_PROMPT_TEMPLATE.format(
        query=query,
        year=year_str,
        era=era or "Unknown",
        location=location,
        setting=setting,
        atmosphere=atmosphere,
        tension_level=tension_level,
        detected_figures=figures_str,
    )

    # Append grounding context if available
    if verified_participants or grounding_notes:
        prompt += "\n\n=== VERIFIED HISTORICAL CONTEXT (from search) ==="
        if verified_participants:
            prompt += f"\nVerified participants: {verified_participants}"
            prompt += "\nUse these verified names. For unnamed characters, use generic period"
            prompt += " identifiers (role-based: 'Baker', 'Guard'), NOT literary character names."
        if grounding_notes:
            prompt += f"\nSetting details: {grounding_notes}"
        prompt += "\n=== END VERIFIED CONTEXT ==="

    return prompt


def get_system_prompt() -> str:
    """Get the system prompt for character identification."""
    return SYSTEM_PROMPT
