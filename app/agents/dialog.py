"""Dialog Agent for dialog generation.

The Dialog Agent creates up to 7 lines of period-appropriate dialog
for the characters in the scene.

Examples:
    >>> from app.agents.dialog import DialogAgent, DialogInput
    >>> agent = DialogAgent()
    >>> result = await agent.run(DialogInput(...))
    >>> for line in result.content.lines:
    ...     print(f"{line.speaker}: {line.text}")

Tests:
    - tests/unit/test_agents/test_dialog.py::test_dialog_max_seven
    - tests/unit/test_agents/test_dialog.py::test_dialog_period_appropriate
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.agents.base import AgentResult, BaseAgent
from app.core.llm_router import LLMRouter
from app.prompts import dialog as dialog_prompts
from app.schemas import CharacterData, DialogData, SceneData, TimelineData


@dataclass
class DialogInput:
    """Input data for Dialog Agent.

    Attributes:
        query: The cleaned query text
        year: Year of the scene
        era: Historical era
        location: Geographic location
        setting: Scene setting description
        atmosphere: Scene atmosphere
        tension_level: Dramatic tension
        speaking_characters: Names of characters who speak
    """

    query: str
    year: int
    era: str | None = None
    location: str = ""
    setting: str = ""
    atmosphere: str = ""
    tension_level: str = "medium"
    speaking_characters: list[str] = field(default_factory=list)

    @classmethod
    def from_data(
        cls,
        query: str,
        timeline: TimelineData,
        scene: SceneData,
        characters: CharacterData,
    ) -> "DialogInput":
        """Create DialogInput from previous agent data.

        Args:
            query: Original/cleaned query
            timeline: TimelineData from Timeline Agent
            scene: SceneData from Scene Agent
            characters: CharacterData from Characters Agent

        Returns:
            DialogInput populated with context
        """
        # Get speaking characters
        speaking = [c.name for c in characters.speaking_characters]
        # If none marked, use primary/secondary
        if not speaking:
            speaking = [c.name for c in characters.primary_characters[:2]]
            speaking.extend([c.name for c in characters.secondary_characters[:2]])

        return cls(
            query=query,
            year=timeline.year,
            era=timeline.era,
            location=timeline.location,
            setting=scene.setting,
            atmosphere=scene.atmosphere,
            tension_level=scene.tension_level,
            speaking_characters=speaking[:4],  # Max 4 speakers
        )


class DialogAgent(BaseAgent[DialogInput, DialogData]):
    """Agent that generates dialog for the scene.

    Creates up to 7 lines of period-appropriate dialog
    with tones, actions, and stage directions.

    Attributes:
        response_model: DialogData Pydantic model
        name: "DialogAgent"

    Dialog Elements:
        - speaker: Character name
        - text: The spoken line
        - tone: Emotional delivery
        - action: Physical action while speaking
        - direction: Stage direction

    Examples:
        >>> agent = DialogAgent()
        >>> result = await agent.run(DialogInput(
        ...     query="signing of the declaration",
        ...     year=1776,
        ...     speaking_characters=["John Hancock", "Benjamin Franklin"]
        ... ))
        >>> len(result.content.lines)  # <= 7

    Tests:
        - tests/unit/test_agents/test_dialog.py::test_dialog_initialization
        - tests/unit/test_agents/test_dialog.py::test_dialog_run
    """

    response_model = DialogData

    def __init__(
        self,
        router: LLMRouter | None = None,
    ) -> None:
        """Initialize Dialog Agent."""
        super().__init__(router=router, name="DialogAgent")

    def get_system_prompt(self) -> str:
        """Get the system prompt for dialog generation."""
        return dialog_prompts.get_system_prompt()

    def get_prompt(self, input_data: DialogInput) -> str:
        """Get the user prompt for dialog generation."""
        return dialog_prompts.get_prompt(
            query=input_data.query,
            year=input_data.year,
            era=input_data.era,
            location=input_data.location,
            setting=input_data.setting,
            atmosphere=input_data.atmosphere,
            tension_level=input_data.tension_level,
            speaking_characters=input_data.speaking_characters,
        )

    async def run(self, input_data: DialogInput) -> AgentResult[DialogData]:
        """Generate dialog for the scene.

        Args:
            input_data: DialogInput with context

        Returns:
            AgentResult containing DialogData
        """
        result = await self._call_llm(input_data, temperature=0.8)

        if result.success and result.content:
            result.metadata["line_count"] = result.content.line_count
            result.metadata["speakers"] = result.content.speakers

        return result
