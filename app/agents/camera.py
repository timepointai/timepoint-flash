"""
Camera controls agent.

Generates cinematic camera directives based on the moment and scene context.
"""
from pydantic import BaseModel, Field
from app.services.google_ai import call_llm
from app.config import settings


class CameraDirectives(BaseModel):
    """Cinematic camera controls for image generation."""
    angle: str = Field(
        ...,
        max_length=100,
        description="Camera angle (eye-level/low-angle/high-angle/dutch-angle/overhead)"
    )
    perspective: str = Field(
        ...,
        max_length=150,
        description="First-person perspective description - camera AS a person in the room at the event"
    )
    lens: str = Field(
        ...,
        max_length=80,
        description="Lens choice (24mm wide/35mm/50mm standard/85mm portrait/200mm telephoto)"
    )
    focal_length_effect: str = Field(
        ...,
        max_length=150,
        description="Visual effect of lens choice (compression, depth of field, distortion)"
    )
    framing: str = Field(
        ...,
        max_length=100,
        description="Shot framing (extreme close-up/close-up/medium/medium-wide/wide/extreme wide)"
    )
    composition: str = Field(
        ...,
        max_length=200,
        description="Compositional guidance (rule of thirds, leading lines, symmetry, golden ratio)"
    )
    depth_of_field: str = Field(
        ...,
        max_length=100,
        description="Depth of field (shallow/medium/deep) and what's in focus"
    )
    lighting_setup: str = Field(
        ...,
        max_length=200,
        description="Gaffer's lighting setup (key light, fill light, rim light, practical lights)"
    )
    camera_movement_frozen: str = Field(
        ...,
        max_length=150,
        description="Implied camera movement frozen in time (tracking shot frozen, dolly zoom effect, handheld feel)"
    )
    immersion_note: str = Field(
        ...,
        max_length=200,
        description="First-person immersion - how the viewer is positioned as a participant in the scene"
    )


async def generate_camera_directives(
    cleaned_query: str,
    moment: dict,
    characters: list,
    setting: dict,
    year: int,
    location: str
) -> CameraDirectives:
    """
    Generate cinematic camera controls for the scene.

    Args:
        cleaned_query: Original query
        moment: Dramatic moment data
        characters: Character list
        setting: Scene setting
        year: Year of scene
        location: Location

    Returns:
        Camera directives for image generation
    """
    # Extract moment context
    plot = moment.get('plot_summary', '')
    action = moment.get('action', '')
    emotional_tone = moment.get('emotional_tone', 'neutral')
    focal_point = moment.get('focal_point', '')

    # Character info
    character_summary = ", ".join([c.get('name', '') for c in characters[:4]])
    num_characters = len(characters)

    system_prompt = f"""You are a cinematographer and director of photography for historical recreations.

Your role:
1. Design camera controls that capture this SPECIFIC MOMENT dramatically
2. CRITICAL: Use FIRST-PERSON perspective - the camera IS a person in the room witnessing this event
3. Position the camera as a participant or observer naturally present in the scene
4. Match camera choices to the emotional tone and action
5. Create immersive, "you are there" cinematography

Scene context:
- Historical moment: {cleaned_query}
- Year: {year}, Location: {location}
- Plot: {plot}
- Action: {action}
- Emotional tone: {emotional_tone}
- Focal point: {focal_point}
- Characters: {character_summary} ({num_characters} total)
- Setting: {setting.get('environment', '')}

FIRST-PERSON PERSPECTIVE RULES:
- The camera is positioned where a real person would be standing/sitting in this scene
- If characters are sitting at a table, the camera sits AT the table, eye-to-eye level
- If characters are standing in conversation, camera is standing with them at eye level
- If this is a crowd scene, camera is IN the crowd at human height
- The viewer should feel like they're physically present in the moment
- Avoid "fly on the wall" or impossible camera positions
- Think: "Where would I be standing/sitting if I was there?"

CRITICAL - IN SITU REALISM (Characters IGNORE the camera):
- Characters should be looking at EACH OTHER, NOT at the camera
- This is documentary/photojournalistic realism - capturing a moment in progress
- Characters are engaged with the scene, not posing for a photo
- Eye contact should be between characters based on their interactions
- Only in rare cases (portrait, direct address) should anyone look at camera
- Default: everyone's attention is on the ACTION and each other, camera is invisible observer

Camera angle guidelines based on scene:
- Eye-level: Most immersive, "person in the room", for conversations and intimate moments
- Low-angle: Character is above camera (looking up), shows power/dominance
- High-angle: Camera above subject (looking down), shows vulnerability
- Use eye-level as default unless emotional tone demands otherwise

Lens choice guidelines:
- Wide (24mm): For establishing shots, environmental context, multiple characters
- Standard (35-50mm): Natural perspective, similar to human vision, intimate conversations
- Portrait (85mm): Character focus, emotional close-ups, isolates subject
- Choose based on how many characters and the intimacy of the moment

Lighting (gaffer) guidelines:
- Match time of day: {setting.get('time_of_day', 'day')}
- Weather: {setting.get('weather', {}).get('condition', 'clear')}
- Use period-appropriate light sources (candles, torches, gas lamps, sunlight)
- Create mood matching: {emotional_tone}

Generate camera directives that make the viewer feel physically present at this historical moment.
"""

    user_prompt = f"Generate first-person camera directives for: {cleaned_query}"

    result = await call_llm(
        model=settings.JUDGE_MODEL,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        response_model=CameraDirectives,
        temperature=0.8,
        max_tokens=4000
    )

    return result
