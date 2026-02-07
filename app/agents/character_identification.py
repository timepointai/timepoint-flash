"""Character Identification Agent for Phase 1 of parallel character generation.

Fast identification of who should be in the scene before parallel bio generation.

Examples:
    >>> from app.agents.character_identification import CharacterIdentificationAgent
    >>> agent = CharacterIdentificationAgent()
    >>> result = await agent.run(CharacterIdentificationInput(...))
    >>> for stub in result.content.characters:
    ...     print(f"{stub.name}: {stub.role.value}")

Tests:
    - tests/unit/test_character_identification.py
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.agents.base import AgentResult, BaseAgent
from app.core.llm_router import LLMRouter
from app.prompts import character_identification as char_id_prompts
from app.schemas import SceneData, TimelineData
from app.schemas.character_identification import CharacterIdentification


@dataclass
class CharacterIdentificationInput:
    """Input data for Character Identification Agent.

    Attributes:
        query: The cleaned query text
        year: Year of the scene
        era: Historical era
        location: Geographic location
        setting: Scene setting description
        atmosphere: Scene atmosphere
        tension_level: Dramatic tension
        detected_figures: Historical figures from Judge
        verified_participants: Verified participants from Grounding Agent
        grounding_notes: Additional historical context from grounding
    """

    query: str
    year: int
    era: str | None = None
    location: str = ""
    setting: str = ""
    atmosphere: str = ""
    tension_level: str = "medium"
    detected_figures: list[str] = field(default_factory=list)
    verified_participants: str = ""
    grounding_notes: str = ""

    @classmethod
    def from_data(
        cls,
        query: str,
        timeline: TimelineData,
        scene: SceneData,
        detected_figures: list[str] | None = None,
        grounded_context: object | None = None,
    ) -> "CharacterIdentificationInput":
        """Create input from previous agent data.

        Args:
            query: Original/cleaned query
            timeline: TimelineData from Timeline Agent
            scene: SceneData from Scene Agent
            detected_figures: Figures detected by Judge
            grounded_context: GroundedContext from Grounding Agent (optional)

        Returns:
            CharacterIdentificationInput populated with context
        """
        verified = ""
        notes = ""
        if grounded_context is not None:
            # Extract verified participant names
            verified_parts = []
            if hasattr(grounded_context, "verified_participants") and grounded_context.verified_participants:
                verified_parts.append("Verified participants: " + ", ".join(grounded_context.verified_participants))
            if hasattr(grounded_context, "physical_participants") and grounded_context.physical_participants:
                verified_parts.append("Physical positions: " + "; ".join(grounded_context.physical_participants))
            verified = "\n".join(verified_parts) if verified_parts else ""

            # Extract richer context from grounding
            notes_parts = []
            if hasattr(grounded_context, "verified_location") and grounded_context.verified_location:
                notes_parts.append(f"Verified location: {grounded_context.verified_location}")
            if hasattr(grounded_context, "verified_date") and grounded_context.verified_date:
                notes_parts.append(f"Verified date: {grounded_context.verified_date}")
            if hasattr(grounded_context, "setting_details") and grounded_context.setting_details:
                notes_parts.append(f"Setting: {grounded_context.setting_details}")
            if hasattr(grounded_context, "event_mechanics") and grounded_context.event_mechanics:
                notes_parts.append(f"Event mechanics: {grounded_context.event_mechanics}")
            notes = "\n".join(notes_parts) if notes_parts else ""

        return cls(
            query=query,
            year=timeline.year,
            era=timeline.era,
            location=timeline.location,
            setting=scene.setting,
            atmosphere=scene.atmosphere,
            tension_level=scene.tension_level,
            detected_figures=detected_figures or [],
            verified_participants=verified,
            grounding_notes=notes,
        )


class CharacterIdentificationAgent(BaseAgent[CharacterIdentificationInput, CharacterIdentification]):
    """Agent that identifies characters for the scene (Phase 1).

    Fast identification of who should appear in the scene.
    Output is used for parallel bio generation in Phase 2.

    Attributes:
        response_model: CharacterIdentification Pydantic model
        name: "CharacterIdentificationAgent"

    Examples:
        >>> agent = CharacterIdentificationAgent()
        >>> result = await agent.run(CharacterIdentificationInput(
        ...     query="assassination of Julius Caesar",
        ...     year=-44,
        ...     detected_figures=["Julius Caesar", "Brutus"]
        ... ))
        >>> len(result.content.characters)  # <= 8

    Tests:
        - tests/unit/test_character_identification.py::test_identification_agent
    """

    response_model = CharacterIdentification

    def __init__(
        self,
        router: LLMRouter | None = None,
    ) -> None:
        """Initialize Character Identification Agent."""
        super().__init__(router=router, name="CharacterIdentificationAgent")

    def get_system_prompt(self) -> str:
        """Get the system prompt for character identification."""
        return char_id_prompts.get_system_prompt()

    def get_prompt(self, input_data: CharacterIdentificationInput) -> str:
        """Get the user prompt for character identification."""
        return char_id_prompts.get_prompt(
            query=input_data.query,
            year=input_data.year,
            era=input_data.era,
            location=input_data.location,
            setting=input_data.setting,
            atmosphere=input_data.atmosphere,
            tension_level=input_data.tension_level,
            detected_figures=input_data.detected_figures,
            verified_participants=input_data.verified_participants,
            grounding_notes=input_data.grounding_notes,
        )

    async def run(
        self, input_data: CharacterIdentificationInput
    ) -> AgentResult[CharacterIdentification]:
        """Identify characters for the scene.

        Args:
            input_data: CharacterIdentificationInput with context

        Returns:
            AgentResult containing CharacterIdentification
        """
        result = await self._call_llm(input_data, temperature=0.5)

        if result.success and result.content:
            result.metadata["character_count"] = len(result.content.characters)
            result.metadata["speaking_count"] = len(result.content.speaking_stubs)
            result.metadata["focal_character"] = result.content.focal_character

        return result
