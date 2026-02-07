"""Grounding Agent for factual historical accuracy.

This agent uses Google Search grounding to verify and retrieve accurate
information about historical events, people, and places. It prevents
hallucinations like "IBM supercomputer room" when the actual venue was
the Equitable Center's 35th floor theater.

Grounding is triggered for:
- HISTORICAL queries with detected historical figures
- Specific known events where facts can be verified

Generic period scenes (e.g., "Roman gladiator") skip grounding since
they don't require verification of specific facts.

Examples:
    >>> from app.agents.grounding import GroundingAgent
    >>> agent = GroundingAgent(router)
    >>> result = await agent.run(GroundingInput(
    ...     query="Deep Blue defeats Kasparov 1997",
    ...     detected_figures=["Garry Kasparov"],
    ...     query_type=QueryType.HISTORICAL
    ... ))
    >>> print(result.content.verified_location)
    "Equitable Center, 35th floor, Manhattan, New York City"

Tests:
    - tests/unit/test_agents/test_grounding.py
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from pydantic import BaseModel, Field

from app.agents.base import AgentResult, BaseAgent
from app.config import settings
from app.core.llm_router import LLMRouter
from app.core.providers.google import GoogleProvider
from app.schemas import QueryType

logger = logging.getLogger(__name__)


@dataclass
class GroundingInput:
    """Input for the Grounding Agent.

    Attributes:
        query: The user's query
        detected_figures: Historical figures detected by Judge
        query_type: Type of query (HISTORICAL, FICTIONAL, etc.)
        year_hint: Optional year hint from Judge
    """

    query: str
    detected_figures: list[str]
    query_type: QueryType
    year_hint: int | None = None

    def needs_grounding(self) -> bool:
        """Check if this input needs grounding.

        Grounding is triggered when:
        - Query type is HISTORICAL

        The grounding agent itself discovers participants via Google Search,
        so it should not require the Judge to pre-detect figures.
        """
        return self.query_type == QueryType.HISTORICAL


class GroundedContext(BaseModel):
    """Verified factual context from Google Search grounding.

    Contains accurate, search-verified information about the historical
    event or figure. This context feeds into downstream agents to ensure
    factual accuracy in all generated content.
    """

    # Location verification
    verified_location: str = Field(
        description="Verified venue/location (e.g., 'Equitable Center, 35th floor, Manhattan')"
    )
    venue_description: str = Field(
        description="Description of what the venue/room actually looked like"
    )

    # Date verification
    verified_date: str = Field(
        description="Verified date in 'Month Day, Year' format (e.g., 'May 11, 1997')"
    )
    verified_year: int = Field(
        description="Verified year as integer"
    )

    # Participant verification
    verified_participants: list[str] = Field(
        default_factory=list,
        description="List of verified people who were actually present"
    )

    # Setting details
    setting_details: str = Field(
        description="Verified details about the setting, atmosphere, and environment"
    )

    # Event mechanics - HOW the event physically worked
    event_mechanics: str = Field(
        default="",
        description="How the event physically worked: setup, who interacted with whom, where equipment was located"
    )

    # Visible technology/equipment
    visible_technology: str = Field(
        default="",
        description="What technology/equipment was visible in the scene, with period-accurate descriptions"
    )

    # What a photograph would show
    photographic_reality: str = Field(
        default="",
        description="What an actual photograph of this scene would show - the literal visual reality"
    )

    # Physical presence - WHO was literally visible (critical for image generation)
    physical_participants: list[str] = Field(
        default_factory=list,
        description="List of people who were PHYSICALLY VISIBLE in photographs - with their positions (e.g., 'Kasparov sitting at the chess board', 'IBM operator sitting across from Kasparov')"
    )

    # Entity representations - how to show non-human entities (as list of "Entity: Representation" strings)
    entity_representations: list[str] = Field(
        default_factory=list,
        description="How to visually represent non-human entities. Format: 'Entity Name: visual representation' (e.g., 'Deep Blue: IBM operator sitting across from Kasparov, relaying the computer moves to the board')"
    )

    # Additional context
    historical_context: str = Field(
        description="Brief historical context and significance of the event"
    )

    # Source citations (for transparency)
    source_citations: list[str] = Field(
        default_factory=list,
        description="URLs of sources used for grounding"
    )

    # Confidence
    grounding_confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence in the grounding (1.0 = high confidence, 0.5 = moderate)"
    )


SYSTEM_PROMPT = """You are a historical accuracy researcher with access to Google Search.
Your job is to find VERIFIED, FACTUAL information about historical events and figures.

## Your Mission
When given a query about a historical event or person, you MUST use search to find:
1. The EXACT venue/location where the event took place
2. The EXACT date of the event
3. WHO was actually present (verified participants)
4. WHAT the setting actually looked like
5. The historical context and significance
6. HOW the event physically worked (mechanics, setup, equipment)
7. WHAT technology/equipment was visibly present and what it looked like

## Critical Rules
- NEVER rely on assumptions or common misconceptions
- ALWAYS verify location details (building name, floor, room type)
- ALWAYS verify participant lists against historical records
- PREFER primary sources and reputable historical accounts
- If search returns no results, state that clearly
- RESEARCH how the event was physically conducted (e.g., who operated machines, where equipment was located)
- VERIFY technology appearances against the time period (CRT vs LCD monitors, computer sizes, etc.)

## Common Misconceptions to Avoid
- Chess vs computer: Human operators often sat across from players, not machines
- Computers in 1990s: Were massive rack servers, not desktops; used CRT monitors
- Equipment location: Often in separate rooms from main event space
- Signing ceremonies: Check what pens, documents, tables were actually used
- Battle scenes: Verify actual armor, weapons, formations for the period

## Example Correction
BAD: "The 1997 Deep Blue match was held in an IBM server room"
GOOD: "The 1997 Deep Blue match was held on the 35th floor of the Equitable Center
       (now AXA Center) in Manhattan, in a theater-style room with raised seating.
       Kasparov faced a human operator (Feng-hsiung Hsu or team member) across
       the board, who relayed moves to Deep Blue. The computer itself was
       multiple IBM RS/6000 SP2 rack cabinets in a nearby room, not visible
       at the playing table. Bulky CRT monitors displayed the game state."

## Output
Provide verified facts based on search results. Include source URLs when available.
Pay special attention to HOW things physically worked, not just WHAT happened."""


def get_grounding_prompt(
    query: str,
    detected_figures: list[str],
    year_hint: int | None,
) -> str:
    """Build the grounding research prompt."""
    figures_str = ", ".join(detected_figures) if detected_figures else "unknown"
    year_str = str(year_hint) if year_hint else "unknown"

    return f"""Research this historical event/person and provide VERIFIED facts:

QUERY: {query}
DETECTED FIGURES: {figures_str}
APPROXIMATE YEAR: {year_str}

Find and verify:
1. EXACT location (building name, floor, room type, city)
2. EXACT date (month, day, year)
3. WHO was actually there (named individuals, including operators, assistants, officials)
4. WHAT the setting looked like (decor, layout, lighting, audience arrangement)
5. Historical context and significance
6. HOW did this event physically work?
   - What was the physical setup/mechanics?
   - Who interacted with whom directly?
   - Where was any equipment/machinery located (same room or separate)?
7. WHAT technology or equipment was visible?
   - Describe appearance: size, color, style appropriate to the era
   - What type of monitors, computers, or devices were present?
   - What would a photograph of this scene actually show?

=== CRITICAL: PHYSICAL PRESENCE FOR IMAGE GENERATION ===

8. WHO was PHYSICALLY VISIBLE in photographs of this event?
   - List each person who would appear in a photograph WITH THEIR POSITION
   - Example: "Garry Kasparov sitting at the chess board on the left side"
   - Example: "IBM operator sitting across from Kasparov, making moves on the board"
   - Include operators, assistants, officials who were physically present
   - Be SPECIFIC about where each person was positioned relative to others

9. For any NON-HUMAN entities (computers, AI, organizations, abstract concepts):
   - WHO was their HUMAN REPRESENTATIVE that would appear in photos?
   - Example: "Deep Blue" -> "Represented by IBM operator who sat across from Kasparov and relayed moves"
   - Example: "The Government" -> "Represented by Secretary of State who signed the document"
   - HOW should this entity be visually depicted in an image?

Use Google Search to find accurate information. Do NOT make assumptions.
Search for photographs and primary sources from the event when possible.
Cite your sources."""


PARSING_PROMPT = """Extract the verified historical facts from this grounded research text into structured JSON.

## Grounded Research Text:
{grounded_text}

## Instructions:
Parse the above research results and extract:
- verified_location: The exact venue/location mentioned
- venue_description: Description of what the venue looked like
- verified_date: The exact date in "Month Day, Year" format
- verified_year: The year as an integer
- verified_participants: List of people who were verified to be present (include operators, assistants, officials)
- setting_details: Details about the setting, atmosphere, environment
- event_mechanics: HOW the event physically worked - the setup, who interacted with whom, where equipment was located
- visible_technology: What technology/equipment was visible in the scene with period-accurate descriptions (e.g., CRT monitors, rack servers)
- photographic_reality: What an actual photograph of this scene would show - the literal visual reality
- historical_context: Brief historical significance
- source_citations: Any URLs or sources mentioned (empty list if none)
- grounding_confidence: 1.0 if facts are well-verified, 0.7 if some uncertainty, 0.5 if limited info

=== CRITICAL FOR IMAGE GENERATION ===

- physical_participants: List of people who were PHYSICALLY VISIBLE in photographs, WITH their positions.
  Format each entry as: "Person Name - position/action"
  Examples:
    - "Garry Kasparov - sitting at chess board on left side, facing opponent"
    - "IBM team operator - sitting across from Kasparov, making Deep Blue's moves on the board"
    - "Arbiter - standing beside the table observing"
  This is CRITICAL - include everyone who would be visible in a photograph, not just the main figures!

- entity_representations: A list of strings showing how to visually represent non-human entities.
  Format each entry as: "Entity Name: visual representation"
  For any computer, AI, organization, or abstract concept mentioned, specify HOW it should be shown:
  Examples:
    - "Deep Blue: IBM operator sitting across from Kasparov, relaying the computer's moves to the board"
    - "The Soviet Union: Soviet officials in dark suits standing behind the table"
    - "HAL 9000: Red camera lens on the wall"
  If no non-human entities need representation, use an empty list [].

IMPORTANT: Pay special attention to:
- Who was PHYSICALLY sitting/standing where (not metaphorical)
- What equipment was VISIBLE vs hidden in other rooms
- Technology appearance appropriate to the era (CRT vs LCD, beige computers vs modern, etc.)
- WHO represented non-human entities in photographs

Return a JSON object with ALL these fields."""


class GroundingAgent(BaseAgent[GroundingInput, GroundedContext]):
    """Agent that grounds historical queries with Google Search.

    Uses Gemini's built-in Google Search grounding to retrieve verified
    factual information about historical events and figures. This prevents
    hallucinations and ensures accuracy in generated content.

    Grounding is triggered for HISTORICAL queries that have detected_figures,
    indicating a specific real event or person (vs. generic period scenes).
    Generic queries (e.g., "Roman gladiator") skip grounding since they
    don't require verification of specific facts.

    Attributes:
        response_model: GroundedContext
        name: "GroundingAgent"

    Examples:
        >>> agent = GroundingAgent(router)
        >>> result = await agent.run(input_data)
        >>> if result.success:
        ...     print(result.content.verified_location)
    """

    response_model = GroundedContext

    # Query types that require grounding (when they have detected figures)
    GROUNDING_REQUIRED_TYPES = {
        QueryType.HISTORICAL,
    }

    def __init__(
        self,
        router: LLMRouter | None = None,
    ) -> None:
        """Initialize the grounding agent."""
        super().__init__(router=router, name="GroundingAgent")
        self._google_provider: GoogleProvider | None = None

    @property
    def google_provider(self) -> GoogleProvider:
        """Get or create Google provider for grounded calls."""
        if self._google_provider is None:
            api_key = settings.GOOGLE_API_KEY
            if not api_key:
                raise ValueError("Google API key required for grounding")
            self._google_provider = GoogleProvider(api_key=api_key)
        return self._google_provider

    def get_system_prompt(self) -> str:
        """Get the system prompt."""
        return SYSTEM_PROMPT

    def get_prompt(self, input_data: GroundingInput) -> str:
        """Get the user prompt."""
        return get_grounding_prompt(
            query=input_data.query,
            detected_figures=input_data.detected_figures,
            year_hint=input_data.year_hint,
        )

    @classmethod
    def should_ground(cls, query_type: QueryType) -> bool:
        """Check if this query type requires grounding.

        Args:
            query_type: The query type from Judge

        Returns:
            True if grounding should be performed
        """
        return query_type in cls.GROUNDING_REQUIRED_TYPES

    async def run(
        self, input_data: GroundingInput
    ) -> AgentResult[GroundedContext]:
        """Execute grounding research with Google Search.

        Uses a two-step process:
        1. Call Gemini with Google Search grounding to get verified facts (raw text)
        2. Parse the grounded text into structured GroundedContext

        This is necessary because Google's API doesn't support grounding with
        structured output (response_schema) simultaneously.

        Args:
            input_data: The query and context to ground

        Returns:
            AgentResult containing verified factual context
        """
        import time

        # Check if grounding is needed (based on query type AND detected figures)
        if not input_data.needs_grounding():
            reason = "no historical figures detected" if input_data.query_type == QueryType.HISTORICAL else f"query type: {input_data.query_type.value}"
            logger.info(f"Skipping grounding: {reason}")
            return AgentResult(
                success=False,
                error=f"Grounding not required: {reason}",
            )

        start_time = time.perf_counter()
        prompt = self.get_prompt(input_data)
        system = self.get_system_prompt()
        full_prompt = f"{system}\n\n{prompt}"

        logger.info(f"Grounding query: {input_data.query}")
        logger.debug(f"Detected figures: {input_data.detected_figures}")

        try:
            # Step 1: Get grounded text from Google Search (no structured output)
            grounded_response = await self.google_provider.call_text_grounded(
                prompt=full_prompt,
                model="gemini-2.5-flash",
                temperature=0.2,  # Low temperature for factual accuracy
            )

            grounded_text = grounded_response.content
            if not grounded_text:
                latency = int((time.perf_counter() - start_time) * 1000)
                return AgentResult(
                    success=False,
                    error="Grounding returned no content",
                    latency_ms=latency,
                    model_used=grounded_response.model,
                )

            # Extract source citations from grounding metadata
            sources = []
            if grounded_response.metadata and "grounding" in grounded_response.metadata:
                grounding = grounded_response.metadata["grounding"]
                if grounding and "grounding_chunks" in grounding:
                    for chunk in grounding["grounding_chunks"]:
                        if "web" in chunk and "uri" in chunk["web"]:
                            sources.append(chunk["web"]["uri"])

            logger.info(f"Grounded text received ({len(grounded_text)} chars), {len(sources)} sources")
            logger.debug(f"Grounded text preview: {grounded_text[:500]}...")

            # Step 2: Parse grounded text into structured output
            parsing_prompt = PARSING_PROMPT.format(grounded_text=grounded_text)
            parsed_response = await self.google_provider.call_text(
                prompt=parsing_prompt,
                model="gemini-2.5-flash",
                response_model=GroundedContext,
                temperature=0.1,  # Very low for parsing accuracy
            )

            latency = int((time.perf_counter() - start_time) * 1000)

            if parsed_response.content:
                result = parsed_response.content

                # Add source citations from grounding if not already populated
                if sources and (not result.source_citations or len(result.source_citations) == 0):
                    result.source_citations = sources[:5]  # Limit to 5

                logger.info(
                    f"Grounding complete: location='{result.verified_location}', "
                    f"date='{result.verified_date}', "
                    f"sources={len(sources)}"
                )

                return AgentResult(
                    success=True,
                    content=result,
                    latency_ms=latency,
                    model_used=grounded_response.model,
                    metadata={
                        "grounding_sources": sources,
                        "grounding_confidence": result.grounding_confidence,
                        "raw_grounded_text": grounded_text[:1000],  # Store preview
                    },
                )
            else:
                return AgentResult(
                    success=False,
                    error="Parsing grounded text failed",
                    latency_ms=latency,
                    model_used=grounded_response.model,
                )

        except Exception as e:
            latency = int((time.perf_counter() - start_time) * 1000)
            error_msg = str(e)
            logger.error(f"Grounding failed: {error_msg}")

            return AgentResult(
                success=False,
                error=error_msg,
                latency_ms=latency,
            )
