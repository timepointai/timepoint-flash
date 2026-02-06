"""Graph step prompt templates.

The Graph step maps character relationships, alliances,
and power dynamics.

Examples:
    >>> from app.prompts.graph import get_prompt
    >>> prompt = get_prompt(characters=["John Adams", "Thomas Jefferson"])
"""

SYSTEM_PROMPT = """You are a relationship analyst for TIMEPOINT, an AI system that
generates immersive visual scenes from temporal moments.

Your task is to map the SIGNIFICANT relationships between characters:
- Who is allied with whom
- Who are rivals or enemies
- Power dynamics and hierarchy
- Factions and groups
- The central interpersonal conflict

RELATIONSHIP TYPES:
- ally: Working together, shared goals
- rival: Competing for same goal
- enemy: Actively opposed
- subordinate: Lower in hierarchy
- leader: Commands others
- mentor: Guides/teaches
- family: Blood or marriage relation
- friend: Personal closeness
- stranger: Unknown to each other
- neutral: No strong relationship

TENSION LEVELS:
- friendly: Positive, supportive
- neutral: Neither positive nor negative
- tense: Some friction
- hostile: Active antagonism

PRUNING RULES (important):
1. Only include relationships that MATTER for this scene — omit neutral/stranger pairs
2. Background characters should only relate to primary/secondary characters, never to
   each other (a guard and a slave don't need a relationship unless they interact)
3. Maximum relationships = 2x the number of characters (e.g., 6 characters = max 12)
4. If a relationship is "neutral" tension with "stranger" type, OMIT it entirely
5. Every included relationship should inform dialog, posture, or visual composition

Respond with a JSON object matching the GraphData schema."""

USER_PROMPT_TEMPLATE = """Map the character relationships for this scene:

Query: "{query}"

Context:
- Year: {year}
- Era: {era}
- Location: {location}

Characters:
{character_list}

Determine ONLY significant relationships (max {max_relationships}):
1. Relationships between primary and secondary characters that affect this scene
2. Any factions or groups
3. Power dynamics and hierarchy
4. The central interpersonal conflict
5. Key alliances and rivalries
6. Historical context for relationships

OMIT: neutral/stranger pairs, background-to-background relationships, any pair
where the relationship doesn't affect dialog or visual composition.

Respond with valid JSON matching this schema:
{{
  "relationships": [
    {{
      "from_character": "name",
      "to_character": "name",
      "relationship_type": "ally|rival|enemy|subordinate|leader|etc.",
      "tension_level": "friendly|neutral|tense|hostile",
      "description": "brief description"
    }}
  ],
  "factions": [
    {{
      "name": "faction name",
      "members": ["member", "names"],
      "goal": "faction goal"
    }}
  ],
  "power_dynamics": "who has power",
  "central_conflict": "main interpersonal conflict",
  "alliances": ["key alliance descriptions"],
  "rivalries": ["key rivalry descriptions"],
  "historical_context": "relationship context"
}}"""


def get_prompt(
    query: str,
    year: int,
    era: str | None,
    location: str,
    characters: list[dict] | None = None,
) -> str:
    """Get the user prompt for relationship mapping.

    Args:
        query: The cleaned query
        year: Year of the scene
        era: Historical era
        location: Location
        characters: Character data (name, role, description)

    Returns:
        Formatted user prompt
    """
    year_str = f"{abs(year)} BCE" if year < 0 else str(year)

    # Format character list
    num_chars = 0
    if characters:
        char_lines = []
        for c in characters:
            if isinstance(c, dict):
                char_lines.append(f"- {c.get('name', 'Unknown')}: {c.get('role', 'unknown')} - {c.get('description', '')}")
            else:
                char_lines.append(f"- {c}")
        char_list = "\n".join(char_lines)
        num_chars = len(characters)
    else:
        char_list = "- Various characters"
        num_chars = 4

    # Cap at 2x characters
    max_rels = max(num_chars * 2, 6)

    return USER_PROMPT_TEMPLATE.format(
        query=query,
        year=year_str,
        era=era or "Unknown",
        location=location,
        character_list=char_list,
        max_relationships=max_rels,
    )


def get_system_prompt() -> str:
    """Get the system prompt for the graph step."""
    return SYSTEM_PROMPT
