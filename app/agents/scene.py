"""Scene Agent for environment generation.

The Scene Agent creates detailed physical environments, atmospheres,
and sensory details for the temporal moment.

Examples:
    >>> from app.agents.scene import SceneAgent, SceneInput
    >>> agent = SceneAgent()
    >>> input_data = SceneInput(
    ...     query="signing of the declaration",
    ...     year=1776,
    ...     location="Independence Hall, Philadelphia"
    ... )
    >>> result = await agent.run(input_data)
    >>> print(result.content.setting)

Tests:
    - tests/unit/test_agents/test_scene.py::test_scene_environment
    - tests/unit/test_agents/test_scene.py::test_scene_sensory_details
"""

from __future__ import annotations

from dataclasses import dataclass

from app.agents.base import AgentResult, BaseAgent
from app.agents.grounding import GroundedContext
from app.core.llm_router import LLMRouter
from app.prompts import scene as scene_prompts
from app.schemas import SceneData, TimelineData


@dataclass
class SceneInput:
    """Input data for Scene Agent.

    Attributes:
        query: The cleaned query text
        year: Year (negative for BCE)
        era: Historical era name
        season: Season name
        time_of_day: Time of day description
        location: Geographic location
        context: Historical context
        grounded_context: Verified facts from Google Search (optional)
    """

    query: str
    year: int
    era: str | None = None
    season: str | None = None
    time_of_day: str | None = None
    location: str = ""
    context: str | None = None
    grounded_context: GroundedContext | None = None  # Verified venue/setting details

    @classmethod
    def from_timeline(
        cls,
        query: str,
        timeline: TimelineData,
        grounded_context: GroundedContext | None = None,
    ) -> "SceneInput":
        """Create SceneInput from TimelineData and optional grounded context.

        Args:
            query: Original/cleaned query
            timeline: TimelineData from Timeline Agent
            grounded_context: Optional verified facts from Google Search

        Returns:
            SceneInput populated with timeline data and grounded context
        """
        # Use grounded location if available (more accurate)
        location = timeline.location
        context = timeline.historical_context

        if grounded_context:
            # Override with verified data - includes venue description
            location = grounded_context.verified_location
            # Enhance context with verified setting details
            context = f"{grounded_context.setting_details} {grounded_context.historical_context}"

        return cls(
            query=query,
            year=timeline.year,
            era=timeline.era,
            season=timeline.season,
            time_of_day=timeline.time_of_day,
            location=location,
            context=context,
            grounded_context=grounded_context,
        )


class SceneAgent(BaseAgent[SceneInput, SceneData]):
    """Agent that generates scene environments.

    Creates detailed physical settings with atmosphere,
    lighting, objects, and sensory details.

    Attributes:
        response_model: SceneData Pydantic model
        name: "SceneAgent"

    Scene Elements Generated:
        - setting: Physical location description
        - atmosphere: Emotional/social mood
        - weather: Weather conditions
        - lighting: Light quality and sources
        - architecture: Architectural details
        - objects: Props and objects in scene
        - sensory_details: Sight, sound, smell, touch

    Examples:
        >>> agent = SceneAgent()
        >>> input_data = SceneInput(
        ...     query="battle of thermopylae",
        ...     year=-480,
        ...     location="Hot Gates pass"
        ... )
        >>> result = await agent.run(input_data)
        >>> print(result.content.atmosphere)
        'Tension and determination before battle'

    Tests:
        - tests/unit/test_agents/test_scene.py::test_scene_initialization
        - tests/unit/test_agents/test_scene.py::test_scene_run
    """

    response_model = SceneData

    def __init__(
        self,
        router: LLMRouter | None = None,
    ) -> None:
        """Initialize Scene Agent."""
        super().__init__(router=router, name="SceneAgent")

    def get_system_prompt(self) -> str:
        """Get the system prompt for scene generation."""
        return scene_prompts.get_system_prompt()

    def get_prompt(self, input_data: SceneInput) -> str:
        """Get the user prompt for scene generation."""
        return scene_prompts.get_prompt(
            query=input_data.query,
            year=input_data.year,
            era=input_data.era,
            season=input_data.season,
            time_of_day=input_data.time_of_day,
            location=input_data.location,
            context=input_data.context,
        )

    async def run(self, input_data: SceneInput) -> AgentResult[SceneData]:
        """Generate the scene environment.

        Args:
            input_data: SceneInput with temporal context

        Returns:
            AgentResult containing SceneData
        """
        result = await self._call_llm(input_data, temperature=0.7)

        if result.success and result.content:
            result.metadata["tension_level"] = result.content.tension_level
            result.metadata["sensory_count"] = len(result.content.sensory_details)

        return result
