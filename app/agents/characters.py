"""Characters Agent for character generation.

The Characters Agent creates up to 8 characters for the scene,
including historical figures and background characters.

Examples:
    >>> from app.agents.characters import CharactersAgent, CharactersInput
    >>> agent = CharactersAgent()
    >>> result = await agent.run(CharactersInput(...))
    >>> for char in result.content.characters:
    ...     print(f"{char.name}: {char.role.value}")

Tests:
    - tests/unit/test_agents/test_characters.py::test_characters_max_eight
    - tests/unit/test_agents/test_characters.py::test_characters_roles
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.agents.base import AgentResult, BaseAgent
from app.core.llm_router import LLMRouter
from app.prompts import characters as characters_prompts
from app.schemas import CharacterData, SceneData, TimelineData


@dataclass
class CharactersInput:
    """Input data for Characters Agent.

    Attributes:
        query: The cleaned query text
        year: Year of the scene
        era: Historical era
        location: Geographic location
        setting: Scene setting description
        atmosphere: Scene atmosphere
        tension_level: Dramatic tension
        detected_figures: Historical figures from Judge
    """

    query: str
    year: int
    era: str | None = None
    location: str = ""
    setting: str = ""
    atmosphere: str = ""
    tension_level: str = "medium"
    detected_figures: list[str] = field(default_factory=list)

    @classmethod
    def from_data(
        cls,
        query: str,
        timeline: TimelineData,
        scene: SceneData,
        detected_figures: list[str] | None = None,
    ) -> "CharactersInput":
        """Create CharactersInput from previous agent data.

        Args:
            query: Original/cleaned query
            timeline: TimelineData from Timeline Agent
            scene: SceneData from Scene Agent
            detected_figures: Figures detected by Judge

        Returns:
            CharactersInput populated with context
        """
        return cls(
            query=query,
            year=timeline.year,
            era=timeline.era,
            location=timeline.location,
            setting=scene.setting,
            atmosphere=scene.atmosphere,
            tension_level=scene.tension_level,
            detected_figures=detected_figures or [],
        )


class CharactersAgent(BaseAgent[CharactersInput, CharacterData]):
    """Agent that generates characters for the scene.

    Creates up to 8 characters with physical descriptions,
    clothing, expressions, and positions.

    Attributes:
        response_model: CharacterData Pydantic model
        name: "CharactersAgent"

    Character Roles:
        - PRIMARY: Main focus characters (1-2)
        - SECONDARY: Important supporting (2-3)
        - BACKGROUND: Atmosphere characters (3-5)

    Examples:
        >>> agent = CharactersAgent()
        >>> result = await agent.run(CharactersInput(
        ...     query="signing of the declaration",
        ...     year=1776,
        ...     detected_figures=["John Hancock", "Benjamin Franklin"]
        ... ))
        >>> len(result.content.characters)  # <= 8

    Tests:
        - tests/unit/test_agents/test_characters.py::test_characters_initialization
        - tests/unit/test_agents/test_characters.py::test_characters_run
    """

    response_model = CharacterData

    def __init__(
        self,
        router: LLMRouter | None = None,
    ) -> None:
        """Initialize Characters Agent."""
        super().__init__(router=router, name="CharactersAgent")

    def get_system_prompt(self) -> str:
        """Get the system prompt for character generation."""
        return characters_prompts.get_system_prompt()

    def get_prompt(self, input_data: CharactersInput) -> str:
        """Get the user prompt for character generation."""
        return characters_prompts.get_prompt(
            query=input_data.query,
            year=input_data.year,
            era=input_data.era,
            location=input_data.location,
            setting=input_data.setting,
            atmosphere=input_data.atmosphere,
            tension_level=input_data.tension_level,
            detected_figures=input_data.detected_figures,
        )

    async def run(self, input_data: CharactersInput) -> AgentResult[CharacterData]:
        """Generate characters for the scene.

        Args:
            input_data: CharactersInput with context

        Returns:
            AgentResult containing CharacterData
        """
        result = await self._call_llm(input_data, temperature=0.7)

        if result.success and result.content:
            result.metadata["character_count"] = len(result.content.characters)
            result.metadata["speaking_count"] = len(result.content.speaking_characters)
            if result.content.focal_character:
                result.metadata["focal_character"] = result.content.focal_character

        return result
