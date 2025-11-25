"""
Character generation agents.

Generates up to 12 unique characters for the scene, each with appearance,
clothing, position, expression, and bio.
"""
from pydantic import BaseModel, Field
from typing import List
from app.services.google_ai import call_llm
from app.config import settings
from app.schemas import Character, CharacterPosition
import asyncio


class CharacterList(BaseModel):
    """List of characters for the scene."""
    characters: List[Character] = Field(..., min_items=1, max_items=12)
    crowd_present: bool = Field(default=False, description="Whether a crowd/background people are present")
    crowd_description: str | None = Field(None, max_length=200, description="Description of the crowd if present")


async def generate_characters(
    cleaned_query: str,
    timeline: dict,
    scene: dict
) -> CharacterList:
    """
    Generate characters for the scene.

    This uses a single LLM call to generate all characters at once for consistency.
    For larger scenes, we could parallelize individual character generation.

    Args:
        cleaned_query: Cleaned query from judge agent
        timeline: Timeline metadata
        scene: Scene context

    Returns:
        CharacterList with 1-12 characters
    """
    system_prompt = f"""You are a character generation agent for a time travel application.

Your role:
1. Identify key historical figures or typical people for this scene
2. Create 1-12 unique characters with diverse appearances and roles
3. Assign spatial positions to each character (x, y, z coordinates 0-1)
4. Ensure period-accurate clothing and appearances
5. Give each character a distinct personality and purpose

Time period: {timeline['year']} {timeline.get('season', 'summer')}
Location: {timeline['location']}
Setting: {scene['setting']['environment']}

Character guidelines:
- Each character must be visually distinct
- Clothing must be period-accurate
- Positions should create an interesting composition
- Include historically significant figures when relevant
- Add "common people" for authenticity
- Maximum 1000 tokens per character (keep bios concise)
- If this is a major event, include key participants
- If a crowd makes sense, set crowd_present=true

Position coordinates:
- x: 0 (left) to 1 (right)
- y: 0 (bottom/front) to 1 (top/back)
- z: 0 (foreground) to 1 (background)
- orientation: "facing camera", "profile left", "profile right", "facing away", etc.

Generate between 1-12 characters depending on the scene's needs."""

    user_prompt = f"Generate characters for: {cleaned_query}"

    result = await call_llm(
        model=settings.JUDGE_MODEL,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        response_model=CharacterList,
        temperature=0.8,  # Higher temp for creativity
        max_tokens=12000  # Increased from 4000 for richer character details
    )

    return result


async def generate_single_character(
    name: str,
    role: str,
    context: str,
    position_hint: dict
) -> Character:
    """
    Generate a single character with full details.

    This can be used for parallel character generation if needed.

    Args:
        name: Character name
        role: Character's role/occupation
        context: Scene context
        position_hint: Suggested position

    Returns:
        Character with full details
    """
    system_prompt = f"""Generate a detailed character description for a time travel scene.

Character: {name}
Role: {role}
Context: {context}

Provide:
- Physical appearance (age, build, distinctive features)
- Period-accurate clothing
- Facial expression
- Body language
- What they're holding/using (if anything)
- Brief bio (background, why they're here)

Keep the total under 1000 tokens."""

    user_prompt = f"Create character: {name} ({role})"

    result = await call_llm(
        model=settings.JUDGE_MODEL,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        response_model=Character,
        temperature=0.8
    )

    return result
