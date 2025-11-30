"""Camera Agent for composition and framing.

The Camera Agent determines visual composition, shot type,
and cinematographic choices for the scene.

Examples:
    >>> from app.agents.camera import CameraAgent, CameraInput
    >>> agent = CameraAgent()
    >>> result = await agent.run(CameraInput(...))
    >>> print(result.content.shot_type)

Tests:
    - tests/unit/test_agents/test_camera.py::test_camera_composition
    - tests/unit/test_agents/test_camera.py::test_camera_shot_types
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.agents.base import AgentResult, BaseAgent
from app.core.llm_router import LLMRouter
from app.prompts import camera as camera_prompts
from app.schemas.camera import CameraData


@dataclass
class CameraInput:
    """Input data for Camera Agent.

    Attributes:
        query: The cleaned query text
        setting: Scene setting
        atmosphere: Scene atmosphere
        tension_level: Dramatic tension
        lighting: Lighting conditions
        focal_point: Suggested focal point
        characters: Character names
    """

    query: str
    setting: str = ""
    atmosphere: str = ""
    tension_level: str = "medium"
    lighting: str | None = None
    focal_point: str | None = None
    characters: list[str] = field(default_factory=list)


class CameraAgent(BaseAgent[CameraInput, CameraData]):
    """Agent that determines visual composition.

    Chooses shot type, camera angle, and compositional
    elements for optimal visual impact.

    Attributes:
        response_model: CameraData Pydantic model
        name: "CameraAgent"

    Composition Elements:
        - shot_type: Wide, medium, close-up, etc.
        - angle: Eye level, low, high, dutch
        - focal_point: Primary visual focus
        - composition_rule: Rule of thirds, etc.
        - depth_of_field: Deep, shallow, selective

    Examples:
        >>> agent = CameraAgent()
        >>> result = await agent.run(CameraInput(
        ...     query="battle of thermopylae",
        ...     tension_level="climactic",
        ...     focal_point="Leonidas"
        ... ))
        >>> print(result.content.shot_type)
        'medium wide'

    Tests:
        - tests/unit/test_agents/test_camera.py::test_camera_initialization
        - tests/unit/test_agents/test_camera.py::test_camera_run
    """

    response_model = CameraData

    def __init__(
        self,
        router: LLMRouter | None = None,
    ) -> None:
        """Initialize Camera Agent."""
        super().__init__(router=router, name="CameraAgent")

    def get_system_prompt(self) -> str:
        """Get the system prompt for camera/composition."""
        return camera_prompts.get_system_prompt()

    def get_prompt(self, input_data: CameraInput) -> str:
        """Get the user prompt for camera/composition."""
        return camera_prompts.get_prompt(
            query=input_data.query,
            setting=input_data.setting,
            atmosphere=input_data.atmosphere,
            tension_level=input_data.tension_level,
            lighting=input_data.lighting,
            focal_point=input_data.focal_point,
            characters=input_data.characters,
        )

    async def run(self, input_data: CameraInput) -> AgentResult[CameraData]:
        """Determine visual composition.

        Args:
            input_data: CameraInput with context

        Returns:
            AgentResult containing CameraData
        """
        result = await self._call_llm(input_data, temperature=0.5)

        if result.success and result.content:
            result.metadata["shot_type"] = result.content.shot_type
            result.metadata["angle"] = result.content.angle

        return result
