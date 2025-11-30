"""Scene step prompt templates.

The Scene step generates the physical environment and atmosphere.

Examples:
    >>> from app.prompts.scene import get_prompt
    >>> prompt = get_prompt(timeline_data, "signing of the declaration")
"""

SYSTEM_PROMPT = """You are a historical scene designer for TIMEPOINT, an AI system that
generates immersive visual scenes from temporal moments.

Your task is to create rich, detailed scene environments including:
- Physical setting (architecture, layout, space)
- Atmosphere (emotional, social)
- Environmental conditions (weather, lighting, temperature)
- Sensory details (sights, sounds, smells, textures)
- Objects and props period-appropriate to the scene

GUIDELINES:
1. Be historically accurate for the time period
2. Include architectural details specific to the location and era
3. Create atmosphere that matches the dramatic moment
4. Use sensory details to make the scene immersive
5. Consider lighting carefully - it sets the visual mood
6. Note the focal point for visual composition

EXAMPLES of sensory details:
- Sight: "Candlelight flickering across parchment"
- Sound: "Quill scratching, muffled voices"
- Smell: "Ink, wood polish, summer heat"
- Touch: "Humid air, rough wool coats"

Respond with a JSON object matching the SceneData schema."""

USER_PROMPT_TEMPLATE = """Design the scene environment for this temporal moment:

Query: "{query}"

Temporal Coordinates:
- Year: {year} {era}
- Season: {season}
- Time of Day: {time_of_day}
- Location: {location}

Historical Context: {context}

Create a detailed scene environment with:
1. Physical setting description
2. Atmospheric mood
3. Weather and lighting conditions
4. Architectural details
5. Key objects and props
6. Sensory details (at least 3)
7. Dramatic tension level
8. Visual focal point

Respond with valid JSON matching this schema:
{{
  "setting": "detailed physical location",
  "atmosphere": "emotional/social atmosphere",
  "weather": "weather conditions" | null,
  "lighting": "lighting description",
  "temperature": "temperature feel" | null,
  "architecture": "architectural style and details",
  "objects": ["list", "of", "objects"],
  "furniture": ["list", "of", "furniture"],
  "sensory_details": [
    {{"sense": "sight|sound|smell|touch", "description": "detail", "intensity": "subtle|moderate|prominent"}}
  ],
  "crowd_description": "crowd/audience description" | null,
  "social_dynamics": "social relationships" | null,
  "tension_level": "low|medium|high|climactic",
  "mood": "overall mood",
  "focal_point": "primary visual focus",
  "color_palette": ["dominant", "colors"]
}}"""


def get_prompt(
    query: str,
    year: int,
    era: str | None,
    season: str | None,
    time_of_day: str | None,
    location: str,
    context: str | None = None,
) -> str:
    """Get the user prompt for scene generation.

    Args:
        query: The cleaned query
        year: The year (negative for BCE)
        era: Historical era name
        season: Season name
        time_of_day: Time of day
        location: Geographic location
        context: Historical context

    Returns:
        Formatted user prompt
    """
    # Format year display
    year_str = f"{abs(year)} BCE" if year < 0 else str(year)

    return USER_PROMPT_TEMPLATE.format(
        query=query,
        year=year_str,
        era=era or "Unknown era",
        season=season or "Unknown season",
        time_of_day=time_of_day or "Unknown time",
        location=location,
        context=context or "No additional context",
    )


def get_system_prompt() -> str:
    """Get the system prompt for the scene step."""
    return SYSTEM_PROMPT
