"""
Scene builder agent.

Creates the setting, weather, lighting, and environmental context for the timepoint.
"""
from pydantic import BaseModel, Field
from typing import List
from app.services.google_ai import call_llm
from app.config import settings


class Weather(BaseModel):
    """Weather conditions."""
    condition: str = Field(..., description="Weather (sunny/cloudy/rainy/snowy/foggy)")
    temperature: str = Field(..., description="Temperature feel (hot/warm/mild/cool/cold)")
    lighting: str = Field(..., description="Lighting quality (bright/soft/dim/dramatic)")


class Setting(BaseModel):
    """Scene setting details."""
    location_type: str = Field(..., description="Type of location (indoor/outdoor/mixed)")
    environment: str = Field(..., description="Environment description (building interior, street, field, etc.)")
    time_of_day: str = Field(..., description="Specific time inferred from context in 12-hour format with AM/PM (e.g., '2:34 PM', '11:47 AM', '8:15 PM')")
    architecture_style: str | None = Field(None, description="Architectural style if applicable")
    time_period_details: str = Field(..., description="Period-specific details (materials, construction, design)")
    atmosphere: str = Field(..., description="Overall atmosphere (bustling/quiet/tense/celebratory)")


class Prop(BaseModel):
    """Important props/objects in the scene."""
    name: str = Field(..., max_length=50)
    description: str = Field(..., max_length=200)
    location: str = Field(..., description="Where it's located in the scene")
    historical_significance: str | None = Field(None, max_length=150)


class SceneContext(BaseModel):
    """Complete scene context."""
    setting: Setting
    weather: Weather
    props: List[Prop] = Field(..., max_length=8, description="Up to 8 important props")
    background_details: str = Field(..., max_length=300, description="Additional background elements")
    historical_context: str = Field(..., max_length=300, description="Historical context for accuracy")


async def build_scene(cleaned_query: str, timeline: dict) -> SceneContext:
    """
    Build the scene setting and context.

    Args:
        cleaned_query: Cleaned query from judge agent
        timeline: Timeline metadata (year, season, location)

    Returns:
        SceneContext with setting, weather, props
    """
    system_prompt = f"""You are a scene builder for a time travel application.

Your role:
1. Create a historically accurate setting for the given time and place
2. Infer a specific time down to the minute from the context (12-hour format with AM/PM)
   - Consider the event type, season, and historical context
   - Be realistic about when events typically occur
   - Examples:
     - "signing of declaration" → "2:17 PM" (formal afternoon event)
     - "punk concert" → "9:42 PM" (evening concert start time)
     - "market scene" → "8:23 AM" (morning market hours)
     - "dinner at restaurant" → "7:15 PM" (typical dinner time)
     - "sunrise ceremony" → "6:14 AM" (dawn event)
     - "midnight raid" → "12:47 AM" (late night)
   - Use varied minutes (not just :00 or :30) for realism
   - Match lighting and atmosphere to the specific time
3. Determine appropriate weather and lighting for the specific time and season
4. Identify important props/objects that should appear in the scene
5. Provide period-accurate details (architecture, materials, design)
6. Set the atmosphere and mood

Time period: {timeline['year']} {timeline.get('season', 'summer')}
Specific Location: {timeline['location']}

CRITICAL RULES FOR LOCATION DETAILS:
- Use the EXACT specific location provided: "{timeline['location']}"
- Reference real architectural features of this specific place
- Include historically accurate details about THIS SPECIFIC LOCATION
- If it's a named building, describe its actual historical appearance
- If it's a named street/area, describe the actual historical environment
- Never use generic descriptions - be specific to the named location

CRITICAL CHARACTER LIMITS:
- background_details: MAXIMUM 300 characters (be concise!)
- historical_context: MAXIMUM 300 characters (be concise!)
- Each prop description: MAXIMUM 200 characters
- Each prop historical_significance: MAXIMUM 150 characters

Focus on:
- Historical accuracy for THIS SPECIFIC LOCATION (architecture, materials, design)
- Visual richness with location-specific details
- Spatial clarity (clear description of this specific environment)
- Period-appropriate details accurate to {timeline['year']}
- Authentic props and objects that would exist at this location
- CONCISE descriptions that stay within character limits

Example: If location is "Borough Market, London", describe the actual medieval market stalls, Thames River proximity, specific merchant types, authentic architecture of that period in that location.

Keep descriptions concise but vivid and SPECIFIC to the named location."""

    user_prompt = f"Build scene context for: {cleaned_query}"

    result = await call_llm(
        model=settings.JUDGE_MODEL,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        response_model=SceneContext,
        temperature=0.7,
        max_tokens=8000  # Explicit limit for detailed scene descriptions
    )

    return result
