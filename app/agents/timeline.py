"""
Timeline/Metadata agent.

Extracts year, season, and generates URL-friendly slug from the cleaned query.
"""
from pydantic import BaseModel, Field
from app.services.google_ai import call_llm
from app.config import settings
import re


class TimelineMetadata(BaseModel):
    """Timeline and metadata extraction result."""
    year: int = Field(..., description="Year of the event (negative for BCE)")
    season: str = Field(..., description="Season (spring/summer/fall/winter) or month")
    slug: str = Field(..., description="URL-friendly slug (lowercase, hyphens)")
    exact_date: str = Field(..., description="Exact date in format 'Month DD, YYYY' (e.g., 'July 15, 1250')")
    time_of_day: str | None = Field(None, description="Time of day (morning/afternoon/evening/night)")
    location: str = Field(..., description="Specific named geographic location (include city, landmark, or building name)")


async def generate_timeline(cleaned_query: str) -> TimelineMetadata:
    """
    Extract timeline metadata from cleaned query.

    Args:
        cleaned_query: Cleaned query from judge agent

    Returns:
        TimelineMetadata with year, season, slug, location
    """
    system_prompt = """You are a timeline extraction agent for a time travel application.

Your role:
1. Extract the year, season/month, and location from the query
2. Generate a URL-friendly slug (lowercase, hyphens, descriptive)
3. ALWAYS generate an exact date - never leave it blank
4. Use specific, named locations - never use generic terms

CRITICAL RULES FOR EXACT DATES:
- ALWAYS provide exact_date in format "Month DD, YYYY" (e.g., "July 15, 1250")
- RESEARCH HISTORICAL EVENTS: If the query mentions a SPECIFIC historical event or person,
  USE YOUR KNOWLEDGE BASE to find the ACTUAL FACTUAL DATE it occurred
- Historical accuracy is CRITICAL - NEVER guess dates for known events
- If only year given (e.g., "1250"), pick a plausible date like "July 15, 1250"
- If year + season given (e.g., "1250 summer"), pick middle of season: "July 20, 1250"
- Never return null or empty for exact_date

RESEARCH THESE TYPES OF EVENTS:
- Famous people arriving somewhere: "Einstein arrives at Princeton" → Research actual date: October 17, 1933
- Historical milestones: "Moon landing" → Research: July 20, 1969
- Political events: "Berlin Wall falls" → Research: November 9, 1989
- Signings/Declarations: "Constitutional Convention signing" → Research: September 17, 1787
- Battles: "Battle of Waterloo" → Research: June 18, 1815
- ANY event with a real historical date - look it up in your knowledge base

CRITICAL RULES FOR LOCATIONS:
- Use specific, named locations - never generic terms like "marketplace" or "tavern"
- If query says "marketplace", determine historically accurate named location (e.g., "Borough Market, London")
- If query says "tavern", pick real historical establishment (e.g., "The White Hart Tavern, London")
- If location is vague, research and pick historically accurate specific place
- Include city names, landmark names, or building names

Examples (showing date research for known events):
- "Einstein arrives at Princeton for the first time" → RESEARCH: October 17, 1933 → year: 1933, season: "fall", exact_date: "October 17, 1933", location: "Princeton University, New Jersey", slug: "einstein-arrives-princeton-university"
- "signing of the constitutional convention" → RESEARCH: September 17, 1787 → year: 1787, season: "summer", exact_date: "September 17, 1787", location: "Pennsylvania State House, Philadelphia", slug: "constitutional-convention-signing"
- "moon landing" → RESEARCH: July 20, 1969 → year: 1969, season: "summer", exact_date: "July 20, 1969", location: "Sea of Tranquility, Moon", slug: "apollo-11-moon-landing"
- "medieval marketplace 1250" → NO SPECIFIC EVENT → year: 1250, season: "summer", exact_date: "July 20, 1250", location: "Borough Market, London", slug: "medieval-borough-market-london"
- "ancient Roman gladiator fight" → NO SPECIFIC EVENT → year: 80, season: "summer", exact_date: "July 15, 80", location: "Colosseum, Rome", slug: "colosseum-gladiator-fight-rome"

For BCE dates, use negative years (e.g., -44 for 44 BCE).
Default to "summer" if season not specified.
Generate descriptive, unique slugs that include location details."""

    user_prompt = f"Extract timeline metadata from: {cleaned_query}"

    result = await call_llm(
        model=settings.JUDGE_MODEL,  # Reuse fast model
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        response_model=TimelineMetadata,
        temperature=0.2,
        max_tokens=4000  # Moderate limit for timeline extraction
    )

    return result


def slugify(text: str) -> str:
    """
    Convert text to URL-friendly slug.

    Args:
        text: Text to slugify

    Returns:
        Lowercase, hyphenated slug
    """
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text.strip('-')
