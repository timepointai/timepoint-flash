"""
Moment/Script generation agent.

Creates a specific plot interaction or dramatic moment for the scene.
This provides narrative structure beyond just setting and characters.
"""
from pydantic import BaseModel, Field
from typing import List
from app.services.google_ai import call_llm
from app.config import settings


class CharacterInteraction(BaseModel):
    """An interaction between two characters."""
    character_a: str = Field(..., max_length=50, description="First character name")
    character_b: str = Field(..., max_length=50, description="Second character name")
    interaction_type: str = Field(..., max_length=100, description="Type of interaction (conversation, confrontation, greeting, etc.)")
    description: str = Field(..., max_length=300, description="What's happening between them")


class NarrativeBeat(BaseModel):
    """A specific story beat/moment in the scene."""
    sequence: int = Field(..., description="Order in the sequence (1-5)")
    action: str = Field(..., max_length=200, description="What's physically happening")
    emotional_tone: str = Field(..., max_length=100, description="Emotional atmosphere of this beat")


class Moment(BaseModel):
    """A specific dramatic moment/interaction in the scene."""
    plot_summary: str = Field(..., max_length=200, description="Brief plot of this specific moment")
    action: str = Field(..., max_length=300, description="What's physically happening right now")
    tension: str = Field(..., max_length=200, description="Dramatic tension or stakes in this moment")
    focal_point: str = Field(..., max_length=150, description="Visual and narrative focal point")
    character_interactions: List[CharacterInteraction] = Field(..., max_length=8, description="Key character-to-character interactions")
    emotional_tone: str = Field(..., max_length=100, description="Overall emotional atmosphere")
    narrative_beats: List[NarrativeBeat] = Field(..., min_length=3, max_length=5, description="3-5 sequential story beats")
    visual_composition: str = Field(..., max_length=300, description="How the scene should be visually composed")
    story_context: str = Field(..., max_length=300, description="Why this moment matters in the larger historical context")


async def generate_moment(
    cleaned_query: str,
    timeline: dict,
    scene: dict,
    characters: list
) -> Moment:
    """
    Generate a specific dramatic moment/interaction for the scene.

    This creates narrative structure and plot beyond just setting and characters.
    It defines what's happening RIGHT NOW in this specific moment.

    Args:
        cleaned_query: Original query
        timeline: Timeline metadata (year, season, location)
        scene: Scene context (setting, weather, props)
        characters: List of characters in the scene

    Returns:
        Moment with plot, interactions, and narrative beats
    """
    character_names = [c['name'] for c in characters]
    character_roles = [f"{c['name']} ({c['role']})" for c in characters]

    system_prompt = f"""You are a moment generation agent for a time travel application.

Your role:
1. Create a specific dramatic moment or interaction for this scene
2. Define what's happening RIGHT NOW (not just the setting)
3. Create interactions between specific characters
4. Provide narrative structure with sequential beats
5. Establish stakes, tension, and focal point
6. Make it cinematically compelling and historically meaningful

Time period: {timeline['year']} {timeline.get('season', 'summer')}
Location: {timeline['location']}
Setting: {scene['setting']['environment']}
Weather: {scene['weather']['condition']}
Characters: {', '.join(character_roles)}

CRITICAL RULES:
- This is a SPECIFIC MOMENT, not a general scene description
- Define WHAT IS HAPPENING RIGHT NOW (action, interaction, event)
- Create 3-5 sequential narrative beats showing progression
- Establish clear character interactions (who talks to whom, who does what)
- Include dramatic tension or stakes
- Make it historically authentic and emotionally engaging
- Visual composition should guide image generation
- Story context explains why this moment matters

Examples of good moments:
- "Benjamin Franklin is presenting his final amendment to the Constitution, while Madison and Hamilton debate intensely"
- "A gladiator is raising his sword victoriously while the crowd roars and the emperor decides his fate"
- "Einstein is writing E=mc² on a blackboard for the first time, explaining it to a skeptical colleague"
- "A medieval merchant is haggling with a noble over a rare spice, while a pickpocket creeps closer"

Available characters: {', '.join(character_names)}"""

    user_prompt = f"Generate a specific dramatic moment for: {cleaned_query}"

    result = await call_llm(
        model=settings.JUDGE_MODEL,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        response_model=Moment,
        temperature=0.85,  # High creativity for narrative
        max_tokens=8000  # Generous limit for detailed moment generation
    )

    return result
