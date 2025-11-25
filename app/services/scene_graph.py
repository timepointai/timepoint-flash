"""
NetworkX scene graph builder.

Creates a graph structure representing spatial and relational connections
between characters, props, and the setting.
"""
import networkx as nx
from networkx.readwrite import json_graph
from typing import List, Dict, Any
import math


def calculate_distance(pos1: dict, pos2: dict) -> float:
    """
    Calculate Euclidean distance between two positions.

    Args:
        pos1: Position dict with x, y, z
        pos2: Position dict with x, y, z

    Returns:
        Distance as float
    """
    dx = pos1['x'] - pos2['x']
    dy = pos1['y'] - pos2['y']
    dz = pos1['z'] - pos2['z']
    return math.sqrt(dx**2 + dy**2 + dz**2)


def are_spatially_close(pos1: dict, pos2: dict, threshold: float = 0.3) -> bool:
    """
    Determine if two positions are spatially close.

    Args:
        pos1: First position
        pos2: Second position
        threshold: Distance threshold for "close"

    Returns:
        True if positions are within threshold
    """
    return calculate_distance(pos1, pos2) < threshold


def build_scene_graph(
    setting: dict,
    weather: dict,
    characters: list,
    props: list
) -> dict:
    """
    Build a NetworkX graph representing the scene.

    The graph structure:
    - Root node: "setting" (the environment)
    - Character nodes: Each character
    - Prop nodes: Each prop
    - Edges: Spatial relationships and interactions

    Args:
        setting: Setting information
        weather: Weather information
        characters: List of character dicts
        props: List of prop dicts

    Returns:
        JSON-serialized graph (node-link format)
    """
    G = nx.DiGraph()

    # Add setting as root node
    G.add_node(
        "setting",
        type="setting",
        **setting,
        weather=weather
    )

    # Add character nodes
    for char in characters:
        G.add_node(
            char['name'],
            type="character",
            **char
        )
        # Connect to setting
        G.add_edge("setting", char['name'], relationship="contains")

    # Add prop nodes
    for prop in props:
        G.add_node(
            prop['name'],
            type="prop",
            **prop
        )
        G.add_edge("setting", prop['name'], relationship="contains")

    # Add character-to-character relationships
    for i, char1 in enumerate(characters):
        for char2 in characters[i+1:]:
            pos1 = char1['position']
            pos2 = char2['position']

            if are_spatially_close(pos1, pos2):
                distance = calculate_distance(pos1, pos2)
                G.add_edge(
                    char1['name'],
                    char2['name'],
                    relationship="near",
                    distance=distance,
                    bidirectional=True
                )

    # Add character-to-prop relationships
    for char in characters:
        # Check if character is holding a prop
        if char.get('key_prop'):
            # Find matching prop
            for prop in props:
                if prop['name'].lower() in char['key_prop'].lower():
                    G.add_edge(
                        char['name'],
                        prop['name'],
                        relationship="holding"
                    )

        # Check if character is near a prop
        for prop in props:
            if 'position' in prop:
                if are_spatially_close(char['position'], prop['position'], threshold=0.2):
                    G.add_edge(
                        char['name'],
                        prop['name'],
                        relationship="near_object"
                    )

    # Serialize to JSON (node-link format for easy reconstruction)
    # Use edges="links" for backward compatibility
    graph_json = json_graph.node_link_data(G, edges="links")

    return graph_json


def graph_to_image_prompt(
    scene_graph: dict,
    cleaned_query: str,
    year: int = None,
    location: str = None,
    moment: dict = None,
    dialog: list = None,
    characters: list = None,
    setting: dict = None,
    weather: dict = None,
    camera: dict = None
) -> str:
    """
    Convert ALL available context into a comprehensive image generation prompt.

    This captures the MOMENT - not just static scene elements, but the emotional
    tone, dramatic action, character interactions, dialogue, and cinematic camera
    controls to create a first-person freeze-frame of the historical event.

    Args:
        scene_graph: JSON-serialized NetworkX graph (spatial relationships)
        cleaned_query: Original cleaned query
        year: Year of the scene (for historical accuracy)
        location: Location of the scene
        moment: Dramatic moment data (plot, action, emotional_tone, interactions, beats)
        dialog: List of dialogue lines with speaker, text, tone
        characters: Full character data with bios, roles, appearance
        setting: Scene setting details
        weather: Weather conditions
        camera: Camera directives (angle, lens, framing, lighting, first-person perspective)

    Returns:
        Comprehensive prompt that captures the dramatic moment with full cinematic control
    """
    prompt_parts = []

    # === SECTION 1: THE MOMENT (Most Important) ===
    if moment:
        prompt_parts.append("=== DRAMATIC MOMENT ===")
        prompt_parts.append(f"Scene: {cleaned_query}")
        prompt_parts.append(f"Plot: {moment.get('plot_summary', '')}")
        prompt_parts.append(f"Action happening RIGHT NOW: {moment.get('action', '')}")
        prompt_parts.append(f"Emotional tone: {moment.get('emotional_tone', 'neutral')}")
        prompt_parts.append(f"Focal point: {moment.get('focal_point', '')}")

        # Narrative beats - the story unfolding
        if moment.get('narrative_beats'):
            beats = [beat.get('description', '') for beat in moment['narrative_beats'][:3]]
            prompt_parts.append(f"Story beats: {'; '.join(beats)}")

        # Visual composition guidance
        if moment.get('visual_composition'):
            prompt_parts.append(f"Visual composition: {moment['visual_composition']}")

        prompt_parts.append("")  # Blank line

    # === SECTION 2: CHARACTER INTERACTIONS & EMOTIONS ===
    if moment and moment.get('character_interactions'):
        prompt_parts.append("=== CHARACTER INTERACTIONS ===")
        for interaction in moment['character_interactions'][:5]:  # Top 5
            char_a = interaction.get('character_a', '')
            char_b = interaction.get('character_b', '')
            desc = interaction.get('description', '')
            emotion_a = interaction.get('emotional_state_a', '')
            emotion_b = interaction.get('emotional_state_b', '')

            prompt_parts.append(
                f"- {char_a} (feeling {emotion_a}) and {char_b} (feeling {emotion_b}): {desc}"
            )
        prompt_parts.append("")

    # === SECTION 3: DIALOGUE (Informs expressions/poses) ===
    if dialog and len(dialog) > 0:
        prompt_parts.append("=== DIALOGUE HAPPENING ===")
        # Include first 3-4 lines to show the conversation dynamic
        for line in dialog[:4]:
            speaker = line.get('speaker', '')
            text = line.get('text', '')[:100]  # Truncate long lines
            tone = line.get('tone', '')
            prompt_parts.append(f'- {speaker} ({tone}): "{text}"')
        prompt_parts.append("")

    # === SECTION 4: CHARACTERS (Full context) ===
    if characters:
        prompt_parts.append("=== CHARACTERS ===")
        for char in characters:
            name = char.get('name', '')
            role = char.get('role', '')
            appearance = char.get('appearance', '')
            clothing = char.get('clothing', '')
            expression = char.get('expression', 'neutral')
            body_language = char.get('body_language', '')
            key_prop = char.get('key_prop', '')
            pos = char.get('position', {})

            # Determine depth position
            z = pos.get('z', 0.5)
            depth = "foreground" if z < 0.3 else "mid-ground" if z < 0.7 else "background"

            char_desc = (
                f"- {name} ({role}): {appearance}. "
                f"Wearing {clothing}. "
                f"Expression: {expression}. "
                f"Body language: {body_language}. "
                f"Position: {depth}."
            )
            if key_prop:
                char_desc += f" Holding: {key_prop}."

            prompt_parts.append(char_desc)
        prompt_parts.append("")

    # === SECTION 5: SETTING & ATMOSPHERE ===
    if setting or weather:
        prompt_parts.append("=== SETTING ===")
        if setting:
            prompt_parts.append(f"Environment: {setting.get('environment', '')}")
            prompt_parts.append(f"Atmosphere: {setting.get('atmosphere', '')}")
            prompt_parts.append(f"Time of day: {setting.get('time_of_day', '')}")
        if weather:
            prompt_parts.append(
                f"Weather: {weather.get('condition', 'clear')}, "
                f"{weather.get('lighting', 'natural')} lighting"
            )
        prompt_parts.append("")

    # === SECTION 6: PROPS (from scene graph) ===
    if scene_graph:
        G = json_graph.node_link_graph(scene_graph, edges="links")
        prop_nodes = [
            (name, data) for name, data in G.nodes(data=True)
            if data.get('type') == 'prop'
        ]

        if prop_nodes:
            prompt_parts.append("=== PROPS & OBJECTS ===")
            for name, data in prop_nodes:
                prompt_parts.append(f"- {name}: {data.get('description', '')}")
            prompt_parts.append("")

    # === SECTION 7: HISTORICAL ACCURACY ===
    if year is not None and location is not None:
        historical_context = _build_historical_accuracy_context(year, location)
        prompt_parts.append(historical_context)
        prompt_parts.append("")

    # === SECTION 8: CAMERA CONTROLS & CINEMATOGRAPHY ===
    if camera:
        prompt_parts.append("=== CAMERA & CINEMATOGRAPHY ===")
        prompt_parts.append(f"Camera angle: {camera.get('angle', 'eye-level')}")
        prompt_parts.append(f"Perspective: {camera.get('perspective', '')}")
        prompt_parts.append(f"Lens: {camera.get('lens', '50mm standard')}")
        prompt_parts.append(f"Lens effect: {camera.get('focal_length_effect', '')}")
        prompt_parts.append(f"Framing: {camera.get('framing', 'medium')}")
        prompt_parts.append(f"Composition: {camera.get('composition', '')}")
        prompt_parts.append(f"Depth of field: {camera.get('depth_of_field', 'medium')}")
        prompt_parts.append(f"Lighting setup (gaffer): {camera.get('lighting_setup', '')}")
        prompt_parts.append(f"Camera movement: {camera.get('camera_movement_frozen', '')}")
        prompt_parts.append(f"FIRST-PERSON IMMERSION: {camera.get('immersion_note', '')}")
        prompt_parts.append("")
        prompt_parts.append("CRITICAL - IN SITU REALISM:")
        prompt_parts.append(
            "Characters are looking at EACH OTHER and focused on their interactions, NOT looking at the camera. "
            "This is photojournalistic/documentary realism capturing a moment in progress. "
            "Characters are engaged in the scene, not posing for a photo. "
            "Eye contact and attention is between characters based on their dialogue and interactions. "
            "The camera is an invisible observer - characters do NOT acknowledge its presence."
        )
        prompt_parts.append("")

    # === SECTION 9: STYLE & TECHNICAL DIRECTIVES ===
    prompt_parts.append("=== STYLE ===")
    prompt_parts.append(
        "Photorealistic, historically accurate, cinematic freeze-frame composition. "
        "Professional photography quality with sharp details, period-appropriate accuracy, "
        "rich colors, dramatic lighting that matches the emotional tone. "
        "Capture facial expressions that reflect the dialogue and emotional states. "
        "Body language and positioning should show the character interactions in progress. "
        "This is a MOMENT IN TIME - show the action happening RIGHT NOW. "
        "The viewer is PHYSICALLY PRESENT in the scene as a first-person participant. "
        "Museum-quality historical recreation with cinematic storytelling."
    )

    return "\n".join(prompt_parts)


def _build_historical_accuracy_context(year: int, location: str) -> str:
    """
    Build historical accuracy instructions for the image generation model.

    This prevents anachronisms in technology, fashion, demographics, and culture.

    Args:
        year: Year of the scene
        location: Geographic location

    Returns:
        Historical accuracy guidance string
    """
    # Determine technology era
    tech_guidance = _get_technology_constraints(year)
    fashion_guidance = _get_fashion_constraints(year)

    context = (
        "CRITICAL HISTORICAL ACCURACY REQUIREMENT: "
        f"This scene is set in {year} in {location}. "
        "\n\n"
        "TECHNOLOGY & OBJECTS:\n"
        f"{tech_guidance}\n"
        "NO anachronistic technology - verify EVERY object existed in this exact year. "
        "If unsure whether something existed, DO NOT include it.\n"
        "\n"
        "CLOTHING & FASHION:\n"
        f"{fashion_guidance}\n"
        "Use period-accurate clothing styles, fabrics, cuts, and accessories. "
        "No modern fashion elements.\n"
        "\n"
        "DEMOGRAPHICS & CULTURE:\n"
        "Use period-accurate demographics, social structures, and cultural norms "
        "that were ACTUALLY present in this specific time and place. "
        "Depict people, relationships, and social structures as they factually existed in this era and location, "
        "reflecting the actual ethnic composition, class structures, and social conventions of the time. "
        "Historical accuracy requires showing what was typical and realistic for this specific context. "
        "Prioritize factual historical authenticity over any other consideration."
    )

    return context


def _get_technology_constraints(year: int) -> str:
    """Get technology constraints based on year."""
    if year >= 2020:
        return "Modern era: smartphones, tablets, wireless earbuds, electric vehicles, laptops, LED screens."
    elif year >= 2000:
        return "Early 2000s: flip phones, early smartphones (after 2007), CRT/early flat screens, desktop computers, digital cameras."
    elif year >= 1990:
        return "1990s: pagers, early cell phones (bulky), landline phones, CRT TVs, VCRs, cassette tapes, early PCs."
    elif year >= 1980:
        return "1980s: landline phones (rotary or touch-tone), cassette tapes, VCRs, arcade games, early computers (very rare), Walkman."
    elif year >= 1970:
        return "1970s: rotary phones, record players, transistor radios, reel-to-reel tape, NO cell phones, NO computers in homes."
    elif year >= 1960:
        return "1960s: rotary phones ONLY, transistor radios, record players, reel-to-reel tape recorders, NO cell phones, NO personal computers, NO calculators (until late 60s)."
    elif year >= 1950:
        return "1950s: rotary phones, AM radios, early TVs (black & white), record players, NO transistors (until late 50s), NO electronics."
    elif year >= 1940:
        return "1940s: rotary phones, tube radios, phonographs, NO TV (very rare until late 40s), NO modern electronics."
    elif year >= 1920:
        return "1920s-1930s: candlestick phones, crystal radios, phonographs, NO TV, NO modern appliances."
    elif year >= 1900:
        return "Early 1900s: early telephones (rare), phonographs (rare), NO radio, NO electric appliances in most homes."
    elif year >= 1850:
        return "Mid-1800s: telegraph (rare), NO telephones, NO photography (very rare), gas lamps, candles for light."
    elif year >= 1800:
        return "1800s: NO electricity, NO phones, NO photos, candles/oil lamps, horse transport, hand tools only."
    elif year >= 1700:
        return "1700s: NO electricity, candles/oil lamps, quill pens, horse/carriage transport, hand tools, sailing ships."
    elif year >= 1600:
        return "1600s: candles, quills, swords, muskets, horse transport, sailing ships, NO modern conveniences."
    elif year >= 1500:
        return "1500s: candles, medieval tools, armor, swords, crossbows, horse transport, sailing ships."
    elif year >= 1000:
        return "Medieval era: torches/candles, swords, armor, castles, horse transport, NO gunpowder in Europe (until 1300s)."
    elif year >= 0:
        return "Ancient/Classical era: oil lamps, torches, swords, shields, chariots, NO stirrups (until ~400 AD), NO gunpowder."
    else:  # BC
        return "Ancient era: torches, oil lamps, primitive weapons (spears, swords, bows), chariots, NO advanced metallurgy."


def _get_fashion_constraints(year: int) -> str:
    """Get fashion/clothing constraints based on year."""
    if year >= 2020:
        return "2020s: athleisure, streetwear, sustainable fashion, gender-neutral styles, sneakers."
    elif year >= 2010:
        return "2010s: skinny jeans, fast fashion, smartphone-influenced accessories, fitness wear."
    elif year >= 2000:
        return "2000s: low-rise jeans, cargo pants, velour tracksuits, trucker hats, chunky highlights."
    elif year >= 1990:
        return "1990s: grunge, baggy jeans, flannel, platform shoes, chokers, minimalism."
    elif year >= 1980:
        return "1980s: shoulder pads, neon colors, leg warmers, power suits, big hair, athletic wear."
    elif year >= 1970:
        return "1970s: bell bottoms, platform shoes, disco fashion, denim everything, earth tones, long hair."
    elif year >= 1960:
        return "1960s: mini skirts, mod fashion, shift dresses, go-go boots, tailored suits for men, NO modern casual wear, NO athleisure."
    elif year >= 1950:
        return "1950s: full skirts, petticoats, saddle shoes, greaser style, conservative suits, formal hats, gloves."
    elif year >= 1940:
        return "1940s: wartime rationing fashion, utility clothing, wide shoulders, knee-length skirts, fedoras, victory rolls."
    elif year >= 1920:
        return "1920s-1930s: flapper dresses, cloche hats, Art Deco, drop-waist dresses, three-piece suits, fedoras."
    elif year >= 1900:
        return "Edwardian era: corsets, long skirts, high collars, bustles, top hats, morning coats, formal gloves."
    elif year >= 1850:
        return "Victorian era: crinolines, corsets, bonnets, waistcoats, frock coats, top hats, NO casual wear."
    elif year >= 1800:
        return "Regency/Empire: high-waisted dresses, spencer jackets, tailcoats, breeches, cravats."
    elif year >= 1700:
        return "18th century: wigs, tricorn hats, knee breeches, waistcoats, stays, panniers, formal court dress."
    elif year >= 1600:
        return "17th century: doublets, ruffs, breeches, falling collars, capes, plumed hats."
    elif year >= 1500:
        return "Renaissance: slashed sleeves, codpieces, ruffs, farthingales, doublets, hose."
    elif year >= 1000:
        return "Medieval: tunics, hose, chainmail, surcoats, wimples, hoods, pointed shoes."
    elif year >= 0:
        return "Classical: togas, tunics, chitons, sandals, cloaks, NO buttons (very rare), draped fabric."
    else:  # BC
        return "Ancient: simple tunics, robes, sandals, primitive weaving, natural dyes, minimal tailoring."
