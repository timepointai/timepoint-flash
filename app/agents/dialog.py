"""
Dialog generation agent.

Creates historically accurate, contextual dialog between characters.
"""
from pydantic import BaseModel, Field
from typing import List
from app.services.google_ai import call_llm
from app.config import settings


class DialogLine(BaseModel):
    """A single line of dialog."""
    speaker: str = Field(..., description="Character name")
    text: str = Field(..., max_length=1500, description="What they say")
    tone: str = Field(..., description="Tone (urgent/calm/excited/thoughtful/etc.)")


class Dialog(BaseModel):
    """Scene dialog."""
    lines: List[DialogLine] = Field(..., min_items=2, max_items=12, description="2-12 lines of dialog")
    context: str = Field(..., max_length=200, description="What's happening in this moment")


async def generate_dialog(
    cleaned_query: str,
    timeline: dict,
    characters: list,
    scene: dict,
    moment: dict
) -> Dialog:
    """
    Generate contextual dialog for the scene.

    Args:
        cleaned_query: Original query
        timeline: Timeline metadata
        characters: List of characters
        scene: Scene context
        moment: Dramatic moment with plot and interactions

    Returns:
        Dialog with 2-12 lines
    """
    character_names = [c['name'] for c in characters]
    character_roles = [f"{c['name']} ({c['role']})" for c in characters]

    # Extract moment context
    plot_summary = moment.get('plot_summary', 'A historical moment')
    action = moment.get('action', 'Characters interact')
    emotional_tone = moment.get('emotional_tone', 'neutral')
    focal_point = moment.get('focal_point', 'the scene')
    character_interactions = moment.get('character_interactions', [])

    # Format interactions for prompt
    interactions_text = ""
    if character_interactions:
        interactions_text = "\n".join([
            f"  - {inter['character_a']} and {inter['character_b']}: {inter['description']}"
            for inter in character_interactions[:5]  # Top 5 interactions
        ])

    system_prompt = f"""You are a dialog generation agent for a time travel application.

Your role:
1. Create historically accurate dialog for this SPECIFIC MOMENT
2. Match speaking style to the time period and social context
3. Reflect each character's personality and role
4. Keep dialog natural and engaging
5. Ensure period-appropriate language (no anachronisms)
6. Make dialog serve the plot and character interactions

Time period: {timeline['year']} {timeline.get('season', 'summer')}
Location: {timeline['location']}
Characters: {', '.join(character_roles)}

SPECIFIC MOMENT CONTEXT:
Plot: {plot_summary}
Action: {action}
Emotional Tone: {emotional_tone}
Focal Point: {focal_point}

CHARACTER INTERACTIONS:
{interactions_text}

Dialog guidelines:
- Use period-appropriate language and speech patterns
- No modern slang or anachronisms
- Each line should advance THIS SPECIFIC MOMENT'S plot
- Reflect the character interactions defined above
- Match the emotional tone: {emotional_tone}
- Keep it concise (2-12 lines total)
- If this is a famous historical moment, reference key themes

Available speakers: {', '.join(character_names)}"""

    user_prompt = f"Generate dialog for this moment: {cleaned_query}"

    result = await call_llm(
        model=settings.JUDGE_MODEL,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        response_model=Dialog,
        temperature=0.9,  # Higher creativity for dialog
        max_tokens=2000  # 2-12 lines @ 1500 chars max = ~2000 tokens sufficient
    )

    return result
