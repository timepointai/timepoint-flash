"""Moment Agent for plot and tension.

The Moment Agent captures the dramatic narrative, stakes,
and emotional arc of the scene.

Examples:
    >>> from app.agents.moment import MomentAgent, MomentInput
    >>> agent = MomentAgent()
    >>> result = await agent.run(MomentInput(...))
    >>> print(result.content.stakes)

Tests:
    - tests/unit/test_agents/test_moment.py::test_moment_narrative
    - tests/unit/test_agents/test_moment.py::test_moment_tension_arc
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.agents.base import AgentResult, BaseAgent
from app.core.llm_router import LLMRouter
from app.prompts import moment as moment_prompts
from app.schemas.moment import MomentData


@dataclass
class MomentInput:
    """Input data for Moment Agent.

    Attributes:
        query: The cleaned query text
        year: Year of the scene
        era: Historical era
        location: Geographic location
        setting: Scene setting
        atmosphere: Scene atmosphere
        characters: Character names
    """

    query: str
    year: int
    era: str | None = None
    location: str = ""
    setting: str = ""
    atmosphere: str = ""
    characters: list[str] = field(default_factory=list)


class MomentAgent(BaseAgent[MomentInput, MomentData]):
    """Agent that captures narrative and dramatic tension.

    Determines what's happening, what's at stake, and
    the emotional arc of the moment.

    Attributes:
        response_model: MomentData Pydantic model
        name: "MomentAgent"

    Narrative Elements:
        - plot_summary: What's happening
        - stakes: What's at risk
        - tension_arc: Rising, falling, climactic, resolved
        - emotional_beats: Key emotions in sequence
        - dramatic_irony: What viewer knows

    Examples:
        >>> agent = MomentAgent()
        >>> result = await agent.run(MomentInput(
        ...     query="signing of the declaration",
        ...     year=1776,
        ...     characters=["John Hancock", "Benjamin Franklin"]
        ... ))
        >>> print(result.content.stakes)
        'The future of American independence'

    Tests:
        - tests/unit/test_agents/test_moment.py::test_moment_initialization
        - tests/unit/test_agents/test_moment.py::test_moment_run
    """

    response_model = MomentData

    def __init__(
        self,
        router: LLMRouter | None = None,
    ) -> None:
        """Initialize Moment Agent."""
        super().__init__(router=router, name="MomentAgent")

    def get_system_prompt(self) -> str:
        """Get the system prompt for moment generation."""
        return moment_prompts.get_system_prompt()

    def get_prompt(self, input_data: MomentInput) -> str:
        """Get the user prompt for moment generation."""
        return moment_prompts.get_prompt(
            query=input_data.query,
            year=input_data.year,
            era=input_data.era,
            location=input_data.location,
            setting=input_data.setting,
            atmosphere=input_data.atmosphere,
            characters=input_data.characters,
        )

    async def run(self, input_data: MomentInput) -> AgentResult[MomentData]:
        """Capture the narrative moment.

        Args:
            input_data: MomentInput with context

        Returns:
            AgentResult containing MomentData
        """
        result = await self._call_llm(input_data, temperature=0.7)

        if result.success and result.content:
            result.metadata["tension_arc"] = result.content.tension_arc
            result.metadata["is_climactic"] = result.content.is_climactic

        return result
