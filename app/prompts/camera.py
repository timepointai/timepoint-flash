"""Camera step prompt templates.

The Camera step determines visual composition, shot type,
and cinematographic choices.

Examples:
    >>> from app.prompts.camera import get_prompt
    >>> prompt = get_prompt("signing of the declaration", focal_point="John Hancock")
"""

SYSTEM_PROMPT = """You are a cinematographer for TIMEPOINT, an AI system that
generates immersive visual scenes from temporal moments.

Your task is to determine the visual composition:
- Shot type and framing
- Camera angle
- Depth of field
- Compositional elements
- Visual hierarchy

SHOT TYPES:
- Extreme wide: Establishing the entire location
- Wide: Full scene with all characters
- Medium wide: Characters from knee up
- Medium: Waist up, conversational
- Medium close-up: Chest up, emotional
- Close-up: Face, intimate
- Extreme close-up: Detail (eyes, hands, objects)

ANGLES:
- Eye level: Neutral, relatable
- Low angle: Power, intimidation
- High angle: Vulnerability, overview
- Dutch angle: Tension, disorientation
- Bird's eye: God-like perspective

COMPOSITION:
- Rule of thirds: Subject at intersection
- Golden ratio: Natural balance
- Symmetry: Formality, power
- Leading lines: Guide the eye
- Frame within frame: Focus, depth

Respond with a JSON object matching the CameraData schema."""

USER_PROMPT_TEMPLATE = """Design the visual composition for this scene:

Query: "{query}"

Scene Context:
- Setting: {setting}
- Atmosphere: {atmosphere}
- Tension: {tension_level}
- Lighting: {lighting}

Focal Point Suggestion: {focal_point}
Characters: {characters}

Determine:
1. Shot type (wide, medium, close-up, etc.)
2. Camera angle
3. Primary and secondary focal points
4. Depth of field
5. Compositional rule to use
6. Foreground, midground, background layers
7. Any camera movement
8. Framing intent

Respond with valid JSON matching this schema:
{{
  "shot_type": "shot type",
  "angle": "camera angle",
  "focal_point": "primary focus",
  "secondary_focus": "secondary focus" | null,
  "depth_of_field": "deep|moderate|shallow|selective",
  "movement": "camera movement" | null,
  "composition_rule": "compositional guideline",
  "leading_lines": ["visual", "lines"],
  "foreground_elements": ["foreground", "items"],
  "midground_elements": ["midground", "items"],
  "background_elements": ["background", "items"],
  "framing_intent": "emotional intent"
}}"""


def get_prompt(
    query: str,
    setting: str,
    atmosphere: str,
    tension_level: str,
    lighting: str | None,
    focal_point: str | None,
    characters: list[str] | None = None,
) -> str:
    """Get the user prompt for camera/composition.

    Args:
        query: The cleaned query
        setting: Scene setting
        atmosphere: Scene atmosphere
        tension_level: Tension level
        lighting: Lighting conditions
        focal_point: Suggested focal point
        characters: Character names

    Returns:
        Formatted user prompt
    """
    char_str = ", ".join(characters) if characters else "Various characters"

    return USER_PROMPT_TEMPLATE.format(
        query=query,
        setting=setting,
        atmosphere=atmosphere,
        tension_level=tension_level,
        lighting=lighting or "Natural lighting",
        focal_point=focal_point or "Main action",
        characters=char_str,
    )


def get_system_prompt() -> str:
    """Get the system prompt for the camera step."""
    return SYSTEM_PROMPT
