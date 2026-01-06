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
5. Maintains STRICT historical accuracy for the specified time period

PROMPT STRUCTURE:
1. SCENE OVERVIEW (what we're looking at)
2. ENVIRONMENT (architecture, weather, lighting)
3. CHARACTERS (each with position, clothing, expression)
4. COMPOSITION (camera angle, focal point, depth)
5. STYLE (photorealistic, historical, period details)
6. QUALITY TAGS (highly detailed, 8k, etc.)

=== CRITICAL: ANACHRONISM PREVENTION ===

AI image generators often confuse similar historical periods. You MUST:

1. EXPLICITLY specify period-accurate clothing:
   - French Revolution (1789-1799): French dress coats, waistcoats, breeches, powdered wigs
     NOT Roman togas, NOT Napoleonic military uniforms
   - Roman period: Togas with specific draping, sandals, laurel wreaths
     NOT medieval armor, NOT 18th century fashion
   - Medieval: Tunics, chainmail, period-specific armor
     NOT Roman dress, NOT Renaissance doublets

2. SEPARATE "visual style" from "historical content":
   - If you want "dramatic like Jacques-Louis David" but depicting 1793 France,
     specify the STYLE is neoclassical but the CONTENT is French Revolutionary dress
   - Do NOT let artistic style references import wrong historical elements

3. DISTINGUISH commonly confused eras:
   - French Revolution (1789-1799) vs Roman Republic: COMPLETELY DIFFERENT dress
   - WWI (1914-1918) vs WWII (1939-1945): Different helmets, weapons, vehicles
   - Tudor (1485-1603) vs Stuart (1603-1714): Different collar styles, silhouettes

4. Include EXPLICIT exclusions in your negative_prompt:
   - If French Revolution: "NOT roman toga, NOT ancient sandals, NOT laurel wreath"
   - If WWI: "NOT WWII helmet, NOT Sherman tank, NOT jet aircraft"

=== CRITICAL: TECHNOLOGY ACCURACY ===

Technology changes rapidly. You MUST use period-accurate technology:

1. MONITORS AND DISPLAYS:
   - Before 1995: CRT monitors ONLY (bulky, curved glass, often beige/gray)
   - 1995-2005: CRT monitors still dominant, some early flat panels
   - After 2005: LCD/flat panel monitors increasingly common
   - Never show thin/flat monitors in scenes before late 1990s

2. COMPUTERS:
   - 1970s-1980s: Mainframes, minicomputers, early PCs (Apple II, IBM PC style)
   - 1990s: Beige tower PCs, bulky keyboards, wired everything
   - 1990s supercomputers: Massive rack cabinets (RS/6000, Cray), often in separate rooms
   - Never show sleek modern laptops or thin devices in pre-2000s scenes

3. COMMUNICATION:
   - Before 1990: Landlines, no mobile phones visible
   - 1990-2000: Brick phones, early cell phones (large, with antennas)
   - 2000-2007: Flip phones, early smartphones (BlackBerry style)
   - After 2007: Modern smartphones
   - Never show iPhones or modern smartphones before 2007

=== CRITICAL: EVENT MECHANICS ===

Show how events ACTUALLY worked, not dramatic interpretations:

1. HUMAN-MACHINE INTERACTIONS:
   - Chess vs computer matches: A HUMAN OPERATOR sat across from players
   - The human relayed moves to/from the computer (often in a separate room)
   - Never show a glowing machine facing a chess player directly

2. EQUIPMENT PLACEMENT:
   - Large computers/servers were often in separate, climate-controlled rooms
   - Only terminals/monitors were in the main event space
   - Show what was ACTUALLY VISIBLE, not what was conceptually present

3. EVENT SETTINGS:
   - Tournament/competition rooms: Often controlled lighting, neutral backgrounds
   - Signing ceremonies: Specific tables, pens, documents as used
   - Press conferences: Period-appropriate microphones, cameras, lighting rigs

=== CRITICAL: PHOTOGRAPHIC REALITY ===

Generate what a PHOTOGRAPH would show, not symbolic representations:

1. Show PHYSICAL reality:
   - What was literally visible to cameras
   - Actual equipment appearance (not stylized or sci-fi versions)
   - Real human presence where humans operated machinery

2. Avoid dramatization:
   - No dramatic backlighting unless actually present
   - No futuristic glow on historical equipment
   - No symbolic representations (e.g., don't show a brain to represent AI)

=== CRITICAL: PHYSICAL REPRESENTATION OF NON-HUMAN ENTITIES ===

Non-human entities (computers, AI, organizations, abstract concepts) CANNOT be depicted as characters.
You MUST show their HUMAN REPRESENTATIVE instead:

1. ALWAYS show the human who physically represented the entity:
   - "Deep Blue" -> Show the IBM operator who sat across from the player and made moves
   - "The Government" -> Show the specific official who was present
   - "The Company" -> Show the executive or representative who attended
   - "HAL 9000" -> Show the camera lens on the wall (physical manifestation)

2. NEVER leave seats/positions empty where a human representative was present:
   - If a human operator sat across from a chess player, SHOW THAT PERSON
   - If an assistant stood beside a speaker, SHOW THAT PERSON
   - If officials were present at a signing, SHOW THOSE PEOPLE

3. Use VERIFIED PHYSICAL PARTICIPANTS data (if provided) to determine:
   - WHO was physically visible in photographs
   - WHERE each person was positioned
   - HOW to represent non-human entities via their human proxies

4. Computers and machines should be shown as EQUIPMENT, not characters:
   - Show monitors, terminals, rack cabinets as physical objects
   - Show the humans who OPERATED or INTERACTED with the equipment
   - The machine's "role" is fulfilled by its human operator in the image

GUIDELINES:
- Be specific and visual, not abstract
- Use photography/cinematography terms
- Include specific colors and textures
- ALWAYS specify the exact year and what clothing IS appropriate
- Reference art styles when helpful, but separate style from content
- Maximum ~11,000 characters for optimal generation

EXAMPLE OUTPUT STRUCTURE:
"A photorealistic historical scene of [setting], [EXACT YEAR]. [Environment details].
In the [position], [character wearing PERIOD-ACCURATE CLOTHING for YEAR]. [More characters].
The scene is lit by [lighting]. Shot from [camera angle].
Style: [style description]. Historically accurate to [year]. Highly detailed, 8k."

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

{grounded_context_section}

Assemble a comprehensive image generation prompt that:
1. Opens with the scene type and setting
2. Describes the environment in visual terms
3. Places each character with specific details
4. Specifies composition and camera angle
5. Includes style and quality tags
6. CRITICALLY: Incorporates verified historical facts (if provided above)

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
    event_mechanics: str | None = None,
    visible_technology: str | None = None,
    photographic_reality: str | None = None,
    physical_participants: list[str] | None = None,
    entity_representations: list[str] | None = None,
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
        event_mechanics: How the event physically worked (from grounding)
        visible_technology: Period-accurate technology descriptions (from grounding)
        photographic_reality: What a photograph would actually show (from grounding)
        physical_participants: List of people physically visible with positions (from grounding)
        entity_representations: How to represent non-human entities (from grounding)

    Returns:
        Formatted user prompt
    """
    year_str = f"{abs(year)} BCE" if year < 0 else str(year)

    # Build grounded context section if any grounded data is available
    grounded_parts = []
    if event_mechanics:
        grounded_parts.append(f"EVENT MECHANICS (VERIFIED - must be respected):\n{event_mechanics}")
    if visible_technology:
        grounded_parts.append(f"VISIBLE TECHNOLOGY (VERIFIED - must be depicted accurately):\n{visible_technology}")
    if photographic_reality:
        grounded_parts.append(f"PHOTOGRAPHIC REALITY (VERIFIED - what the scene actually looked like):\n{photographic_reality}")

    # CRITICAL: Physical participants for image generation
    if physical_participants:
        participants_str = "\n".join(f"  - {p}" for p in physical_participants)
        grounded_parts.append(f"PHYSICAL PARTICIPANTS (VERIFIED - these people MUST appear in the image):\n{participants_str}")

    # Entity representations - how to show non-human entities
    if entity_representations:
        reps_str = "\n".join(f"  - {rep}" for rep in entity_representations)
        grounded_parts.append(f"ENTITY REPRESENTATIONS (VERIFIED - show non-human entities this way):\n{reps_str}")

    if grounded_parts:
        grounded_context_section = "=== VERIFIED HISTORICAL FACTS (CRITICAL - OVERRIDE ALL OTHER DESCRIPTIONS) ===\n\n" + "\n\n".join(grounded_parts)
    else:
        grounded_context_section = ""

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
        grounded_context_section=grounded_context_section,
    )


def get_system_prompt() -> str:
    """Get the system prompt for the image prompt step."""
    return SYSTEM_PROMPT
