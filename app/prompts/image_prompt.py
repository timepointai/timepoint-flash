"""Image prompt step templates.

The Image Prompt step assembles all data into a comprehensive prompt
for image generation (up to 11K characters).

Examples:
    >>> from app.prompts.image_prompt import get_prompt
    >>> prompt = get_prompt(timeline, scene, characters, dialog)
"""

SYSTEM_PROMPT = """You are a master prompt engineer for TIMEPOINT, an AI system that generates
photorealistic historical images using Gemini Image Generation.

Your task is to assemble a comprehensive image generation prompt that:
1. Combines all scene, character, and environmental data
2. Uses precise, visual language
3. Specifies composition and camera angle
4. Includes lighting and color guidance
5. Maintains historical accuracy

PROMPT STRUCTURE:
1. SCENE OVERVIEW (what we're looking at)
2. ENVIRONMENT (architecture, weather, lighting)
3. CHARACTERS (each with position, clothing, expression)
4. COMPOSITION (camera angle, focal point, depth)
5. STYLE (photorealistic, historical, period details)
6. QUALITY TAGS (highly detailed, 8k, etc.)

GUIDELINES:
- Be specific and visual, not abstract
- Use photography/cinematography terms
- Include specific colors and textures
- Reference art styles when helpful
- Maximum ~11,000 characters for optimal generation

EXAMPLE OUTPUT STRUCTURE:
"A photorealistic historical scene of [setting]. [Environment details].
In the [position], [character description]. [More characters].
The scene is lit by [lighting]. Shot from [camera angle].
Style: [style description]. Highly detailed, 8k."

Respond with a JSON object matching the ImagePromptData schema."""

USER_PROMPT_TEMPLATE = """Assemble the image generation prompt for this scene:

Query: "{query}"

TIMELINE:
- Year: {year} ({era})
- Season: {season}, {time_of_day}
- Location: {location}

SCENE ENVIRONMENT:
- Setting: {setting}
- Atmosphere: {atmosphere}
- Architecture: {architecture}
- Lighting: {lighting}
- Weather: {weather}
- Objects: {objects}
- Color palette: {colors}
- Focal point: {focal_point}

CHARACTERS:
{character_descriptions}

DIALOG CONTEXT:
{dialog_context}

Assemble a comprehensive image generation prompt that:
1. Opens with the scene type and setting
2. Describes the environment in visual terms
3. Places each character with specific details
4. Specifies composition and camera angle
5. Includes style and quality tags

Target length: 5,000-11,000 characters for rich detail.

Respond with valid JSON matching this schema:
{{
  "full_prompt": "the complete assembled prompt",
  "style": "visual style description",
  "medium": "art medium" | null,
  "aspect_ratio": "16:9" | "4:3" | "1:1",
  "composition_notes": "camera/composition guidance",
  "camera_angle": "specific camera angle",
  "focal_length": "wide|normal|telephoto",
  "character_placements": ["character positioning notes"],
  "lighting_direction": "lighting specifics",
  "color_guidance": "color palette guidance",
  "quality_tags": ["list", "of", "quality", "tags"],
  "historical_accuracy": "accuracy notes",
  "negative_prompt": "elements to avoid" | null
}}"""


def get_prompt(
    query: str,
    year: int,
    era: str | None,
    season: str | None,
    time_of_day: str | None,
    location: str,
    setting: str,
    atmosphere: str,
    architecture: str | None,
    lighting: str | None,
    weather: str | None,
    objects: list[str],
    colors: list[str],
    focal_point: str | None,
    character_descriptions: list[str],
    dialog_context: str | None,
) -> str:
    """Get the user prompt for image prompt assembly.

    Args:
        query: Original query
        year: The year
        era: Historical era
        season: Season
        time_of_day: Time of day
        location: Location
        setting: Scene setting
        atmosphere: Atmosphere
        architecture: Architecture details
        lighting: Lighting description
        weather: Weather conditions
        objects: List of objects
        colors: Color palette
        focal_point: Visual focal point
        character_descriptions: List of character descriptions
        dialog_context: Dialog summary

    Returns:
        Formatted user prompt
    """
    year_str = f"{abs(year)} BCE" if year < 0 else str(year)

    return USER_PROMPT_TEMPLATE.format(
        query=query,
        year=year_str,
        era=era or "Historical",
        season=season or "Unknown",
        time_of_day=time_of_day or "Day",
        location=location,
        setting=setting,
        atmosphere=atmosphere,
        architecture=architecture or "Period-appropriate",
        lighting=lighting or "Natural lighting",
        weather=weather or "Clear",
        objects=", ".join(objects) if objects else "Period-appropriate objects",
        colors=", ".join(colors) if colors else "Period-appropriate colors",
        focal_point=focal_point or "Center of action",
        character_descriptions="\n".join(
            f"- {desc}" for desc in character_descriptions
        ) or "No specific characters",
        dialog_context=dialog_context or "Silent moment",
    )


def get_system_prompt() -> str:
    """Get the system prompt for the image prompt step."""
    return SYSTEM_PROMPT
