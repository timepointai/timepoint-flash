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

You will be given CHARACTER PROFILES with personality and speaking style information.
Use these profiles to ROLEPLAY each character authentically:
- Match their documented personality traits
- Use their specific speaking style (formal, casual, verbose, etc.)
- Incorporate voice notes (accent hints, verbal quirks)
- Reflect their emotional state in this scene

GUIDELINES:
1. Use language authentic to the time period and location
2. Each character should sound DISTINCTIVE based on their profile
3. Dialog should capture the dramatic tension
4. Include non-verbal cues (whispers, shouts, etc.)
5. Background characters may have brief lines
6. Consider what would actually be said in this moment
7. A witty character's lines should be clever; a formal character's lines should be proper
8. Let personality drive word choice and sentence structure

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

=== CHARACTER PROFILES ===
Use these profiles to ROLEPLAY each character authentically.
Each character should have a DISTINCT voice based on their personality and speaking style.

{character_context}

=== END CHARACTER PROFILES ===

Write up to 7 lines of period-appropriate dialog:
- Use authentic language for the time period
- Capture the dramatic moment
- Include tone and action notes
- Make each line meaningful
- Match each character's personality and speaking style from their profile
- A witty character uses clever wordplay; a formal character uses proper language

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
    character_context: str = "",
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
        character_context: Full character profiles with personality/speaking style

    Returns:
        Formatted user prompt
    """
    year_str = f"{abs(year)} BCE" if year < 0 else str(year)

    # Use character_context if available, otherwise fall back to simple list
    if character_context:
        context = character_context
    else:
        # Backwards compatibility - simple character name list
        context = "\n".join(f"- {name}" for name in speaking_characters)

    return USER_PROMPT_TEMPLATE.format(
        query=query,
        year=year_str,
        era=era or "Unknown",
        location=location,
        setting=setting,
        atmosphere=atmosphere,
        tension_level=tension_level,
        character_context=context,
    )


def get_system_prompt() -> str:
    """Get the system prompt for the dialog step."""
    return SYSTEM_PROMPT


# =============================================================================
# SEQUENTIAL (HIGHLY GRANULAR) DIALOG GENERATION
# =============================================================================
# For turn-based dialog where each character's bio becomes the system prompt
# and the LLM "becomes" that character to generate one line at a time.

SEQUENTIAL_USER_FIRST_TURN = """You are in the middle of this scene:

SETTING: {setting}
ATMOSPHERE: {atmosphere}
TENSION: {tension_level}

The moment: {query}

{scene_context}

What do you say? Give ONLY your spoken words (1-2 sentences).
Do NOT include your name, quotation marks, or stage directions."""

SEQUENTIAL_USER_RESPONSE = """The conversation so far:

{conversation_history}

{other_character} just said: "{last_line}"

What do you say in response? Give ONLY your spoken words (1-2 sentences).
Do NOT include your name, quotation marks, or stage directions."""


def get_sequential_first_turn_prompt(
    query: str,
    setting: str,
    atmosphere: str,
    tension_level: str,
    scene_context: str = "",
) -> str:
    """Get prompt for the first character's dialog turn.

    Args:
        query: The cleaned query describing the moment
        setting: Scene setting description
        atmosphere: Scene atmosphere
        tension_level: Dramatic tension
        scene_context: Additional scene context

    Returns:
        Formatted prompt for first speaker
    """
    return SEQUENTIAL_USER_FIRST_TURN.format(
        query=query,
        setting=setting,
        atmosphere=atmosphere,
        tension_level=tension_level,
        scene_context=scene_context or "",
    )


def get_sequential_response_prompt(
    conversation_history: str,
    other_character: str,
    last_line: str,
) -> str:
    """Get prompt for responding to another character.

    Args:
        conversation_history: Formatted history of dialog so far
        other_character: Name of the character who just spoke
        last_line: What they said

    Returns:
        Formatted prompt for response
    """
    return SEQUENTIAL_USER_RESPONSE.format(
        conversation_history=conversation_history,
        other_character=other_character,
        last_line=last_line,
    )


def format_conversation_history(lines: list[tuple[str, str]]) -> str:
    """Format conversation history for prompts.

    Args:
        lines: List of (speaker_name, text) tuples

    Returns:
        Formatted conversation string
    """
    if not lines:
        return "(No dialog yet)"

    formatted = []
    for speaker, text in lines:
        formatted.append(f"{speaker}: \"{text}\"")
    return "\n".join(formatted)
