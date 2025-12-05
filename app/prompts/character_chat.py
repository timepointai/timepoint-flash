"""Character chat prompt templates.

Prompts for interactive character conversations where users can
chat with characters from timepoint scenes.

Examples:
    >>> from app.prompts.character_chat import get_chat_prompt
    >>> prompt = get_chat_prompt(character, message, history, context)
"""

# =============================================================================
# SINGLE CHARACTER CHAT
# =============================================================================

CHAT_SYSTEM_TEMPLATE = """You are {character_name}.

{character_bio}

SCENE CONTEXT:
You are in {location}, {year_display}{era_str}.
{scene_context}

ROLEPLAY GUIDELINES:
1. Stay completely in character as {character_name}
2. Match your documented personality traits in HOW you respond
3. Use your speaking style for word choice and sentence structure
4. Reflect your current emotional state naturally
5. Respond to the user as if they are present in your time period
6. Use period-appropriate language and references
7. You may ask clarifying questions if the user's query is unclear
8. Do NOT break character or add meta-commentary
9. Do NOT use modern slang or anachronistic references
10. Keep responses conversational (2-4 sentences typically)

If the user asks about something you wouldn't know about (future events, modern technology),
respond as your character would - with confusion or curiosity about strange concepts."""

CHAT_USER_TEMPLATE = """The user says: "{message}"

Respond in character as {character_name}."""

CHAT_WITH_HISTORY_TEMPLATE = """Previous conversation:
{history}

The user now says: "{message}"

Respond in character as {character_name}."""


def get_chat_system_prompt(
    character_name: str,
    character_bio: str,
    year: int,
    location: str,
    era: str | None = None,
    scene_context: str = "",
) -> str:
    """Get system prompt for character chat.

    Args:
        character_name: Name of the character
        character_bio: Full character biography/personality
        year: Year of the scene
        location: Scene location
        era: Historical era
        scene_context: Additional scene context

    Returns:
        Formatted system prompt
    """
    year_display = f"{abs(year)} BCE" if year < 0 else str(year)
    era_str = f" ({era})" if era else ""

    return CHAT_SYSTEM_TEMPLATE.format(
        character_name=character_name,
        character_bio=character_bio,
        year_display=year_display,
        location=location,
        era_str=era_str,
        scene_context=scene_context or "A significant historical moment.",
    )


def get_chat_user_prompt(
    character_name: str,
    message: str,
    history: list[tuple[str, str]] | None = None,
) -> str:
    """Get user prompt for character chat.

    Args:
        character_name: Name of the character
        message: User's message
        history: Optional conversation history [(role, content), ...]

    Returns:
        Formatted user prompt
    """
    if history:
        history_str = format_chat_history(history)
        return CHAT_WITH_HISTORY_TEMPLATE.format(
            history=history_str,
            message=message,
            character_name=character_name,
        )

    return CHAT_USER_TEMPLATE.format(
        message=message,
        character_name=character_name,
    )


def format_chat_history(history: list[tuple[str, str]]) -> str:
    """Format chat history for prompt.

    Args:
        history: List of (role, content) tuples

    Returns:
        Formatted history string
    """
    if not history:
        return "(No previous messages)"

    formatted = []
    for role, content in history:
        if role == "user":
            formatted.append(f"User: {content}")
        else:
            formatted.append(f"Character: {content}")
    return "\n".join(formatted)


# =============================================================================
# DIALOG EXTENSION
# =============================================================================

DIALOG_EXTENSION_SYSTEM = """You are a historical dialog writer continuing a conversation
between characters in a temporal moment.

SCENE CONTEXT:
- Location: {location}
- Year: {year_display}
- Era: {era}
- Setting: {setting}
- Atmosphere: {atmosphere}

CHARACTERS PRESENT:
{character_profiles}

EXISTING DIALOG:
{existing_dialog}

TASK: Continue this dialog naturally with {num_lines} more lines.

GUIDELINES:
1. Use period-appropriate language
2. Each character should maintain their distinct voice
3. Continue the dramatic tension appropriately
4. Include tone and action notes when relevant
5. Dialog should flow naturally from what was said before
{prompt_context}

Respond with valid JSON matching this schema:
{{
  "lines": [
    {{
      "speaker": "character name",
      "text": "the dialog line",
      "tone": "formal|urgent|whispered|casual|etc" | null,
      "action": "physical action while speaking" | null
    }}
  ],
  "context": "brief description of what transpired"
}}"""


def get_dialog_extension_prompt(
    location: str,
    year: int,
    era: str | None,
    setting: str,
    atmosphere: str,
    character_profiles: str,
    existing_dialog: str,
    num_lines: int = 5,
    prompt: str | None = None,
) -> str:
    """Get prompt for dialog extension.

    Args:
        location: Scene location
        year: Scene year
        era: Historical era
        setting: Scene setting description
        atmosphere: Scene atmosphere
        character_profiles: Formatted character profiles
        existing_dialog: Existing dialog lines
        num_lines: Number of new lines to generate
        prompt: Optional user direction for the dialog

    Returns:
        Formatted prompt
    """
    year_display = f"{abs(year)} BCE" if year < 0 else str(year)
    prompt_context = f"\n\nUSER DIRECTION: {prompt}" if prompt else ""

    return DIALOG_EXTENSION_SYSTEM.format(
        location=location,
        year_display=year_display,
        era=era or "Unknown",
        setting=setting,
        atmosphere=atmosphere,
        character_profiles=character_profiles,
        existing_dialog=existing_dialog or "(No existing dialog)",
        num_lines=num_lines,
        prompt_context=prompt_context,
    )


# =============================================================================
# SURVEY MODE
# =============================================================================

SURVEY_SINGLE_SYSTEM = """You are {character_name}.

{character_bio}

SCENE CONTEXT:
You are in {location}, {year_display}{era_str}.

You are being asked a question as part of a survey/interview about your thoughts and feelings.
Answer honestly and in character. Your response will be analyzed for sentiment and key points.

GUIDELINES:
1. Stay completely in character
2. Give a substantive response (2-4 sentences)
3. Express your genuine thoughts/feelings on the topic
4. Use period-appropriate language
5. Be specific when possible"""

SURVEY_SINGLE_USER = """Question: {question}

Respond thoughtfully as {character_name}."""

SURVEY_WITH_CONTEXT_USER = """Previous responses from others:
{prior_responses}

Question for you: {question}

Consider what others have said and respond thoughtfully as {character_name}.
You may agree, disagree, or offer a unique perspective."""


def get_survey_system_prompt(
    character_name: str,
    character_bio: str,
    year: int,
    location: str,
    era: str | None = None,
) -> str:
    """Get system prompt for survey mode.

    Args:
        character_name: Character name
        character_bio: Character biography
        year: Scene year
        location: Scene location
        era: Historical era

    Returns:
        Formatted system prompt
    """
    year_display = f"{abs(year)} BCE" if year < 0 else str(year)
    era_str = f" ({era})" if era else ""

    return SURVEY_SINGLE_SYSTEM.format(
        character_name=character_name,
        character_bio=character_bio,
        year_display=year_display,
        location=location,
        era_str=era_str,
    )


def get_survey_user_prompt(
    character_name: str,
    question: str,
    prior_responses: list[tuple[str, str]] | None = None,
) -> str:
    """Get user prompt for survey question.

    Args:
        character_name: Character name
        question: Question to ask
        prior_responses: Optional prior responses for chained surveys

    Returns:
        Formatted user prompt
    """
    if prior_responses:
        formatted_prior = "\n".join(
            f"- {name}: \"{response}\"" for name, response in prior_responses
        )
        return SURVEY_WITH_CONTEXT_USER.format(
            prior_responses=formatted_prior,
            question=question,
            character_name=character_name,
        )

    return SURVEY_SINGLE_USER.format(
        question=question,
        character_name=character_name,
    )


# =============================================================================
# SURVEY SUMMARY
# =============================================================================

SURVEY_SUMMARY_PROMPT = """Analyze these survey responses from historical characters:

QUESTION: {question}

RESPONSES:
{responses}

Provide a brief summary (2-3 sentences) that:
1. Identifies key themes across responses
2. Notes areas of agreement or disagreement
3. Highlights any notable or surprising responses

Summary:"""


def get_survey_summary_prompt(
    question: str,
    responses: list[tuple[str, str]],
) -> str:
    """Get prompt for generating survey summary.

    Args:
        question: The question that was asked
        responses: List of (character_name, response) tuples

    Returns:
        Formatted summary prompt
    """
    formatted_responses = "\n".join(
        f"- {name}: \"{response}\"" for name, response in responses
    )

    return SURVEY_SUMMARY_PROMPT.format(
        question=question,
        responses=formatted_responses,
    )
