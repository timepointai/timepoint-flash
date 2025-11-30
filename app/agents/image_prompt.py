"""Image Prompt Agent for prompt assembly.

The Image Prompt Agent assembles all scene data into a comprehensive
prompt for image generation (up to 11k characters).

Examples:
    >>> from app.agents.image_prompt import ImagePromptAgent, ImagePromptInput
    >>> agent = ImagePromptAgent()
    >>> result = await agent.run(ImagePromptInput(...))
    >>> print(result.content.full_prompt[:100])

Tests:
    - tests/unit/test_agents/test_image_prompt.py::test_prompt_assembly
    - tests/unit/test_agents/test_image_prompt.py::test_prompt_length
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.agents.base import AgentResult, BaseAgent
from app.core.llm_router import LLMRouter
from app.prompts import image_prompt as image_prompt_prompts
from app.schemas import (
    CharacterData,
    DialogData,
    ImagePromptData,
    SceneData,
    TimelineData,
)


@dataclass
class ImagePromptInput:
    """Input data for Image Prompt Agent.

    Contains all the data needed to assemble a complete image prompt.
    """

    query: str
    year: int
    era: str | None = None
    season: str | None = None
    time_of_day: str | None = None
    location: str = ""
    setting: str = ""
    atmosphere: str = ""
    architecture: str | None = None
    lighting: str | None = None
    weather: str | None = None
    objects: list[str] = field(default_factory=list)
    colors: list[str] = field(default_factory=list)
    focal_point: str | None = None
    character_descriptions: list[str] = field(default_factory=list)
    dialog_context: str | None = None

    @classmethod
    def from_data(
        cls,
        query: str,
        timeline: TimelineData,
        scene: SceneData,
        characters: CharacterData,
        dialog: DialogData | None = None,
    ) -> "ImagePromptInput":
        """Create ImagePromptInput from all previous agent data.

        Args:
            query: Original/cleaned query
            timeline: TimelineData from Timeline Agent
            scene: SceneData from Scene Agent
            characters: CharacterData from Characters Agent
            dialog: DialogData from Dialog Agent (optional)

        Returns:
            ImagePromptInput with all context assembled
        """
        # Build character descriptions
        char_descriptions = [c.to_prompt_description() for c in characters.characters]

        # Build dialog context
        dialog_context = None
        if dialog:
            dialog_context = dialog.to_script()

        return cls(
            query=query,
            year=timeline.year,
            era=timeline.era,
            season=timeline.season,
            time_of_day=timeline.time_of_day,
            location=timeline.location,
            setting=scene.setting,
            atmosphere=scene.atmosphere,
            architecture=scene.architecture,
            lighting=scene.lighting,
            weather=scene.weather,
            objects=scene.objects,
            colors=scene.color_palette,
            focal_point=scene.focal_point,
            character_descriptions=char_descriptions,
            dialog_context=dialog_context,
        )


class ImagePromptAgent(BaseAgent[ImagePromptInput, ImagePromptData]):
    """Agent that assembles the final image generation prompt.

    Combines all scene data into a comprehensive, detailed prompt
    suitable for high-quality image generation.

    Attributes:
        response_model: ImagePromptData Pydantic model
        name: "ImagePromptAgent"

    Prompt Structure:
        - Style and medium
        - Scene setting and atmosphere
        - Lighting and weather
        - Character descriptions and positions
        - Compositional focus
        - Color palette

    Examples:
        >>> agent = ImagePromptAgent()
        >>> result = await agent.run(ImagePromptInput(...))
        >>> len(result.content.full_prompt)  # Up to ~11k chars

    Tests:
        - tests/unit/test_agents/test_image_prompt.py::test_initialization
        - tests/unit/test_agents/test_image_prompt.py::test_run
    """

    response_model = ImagePromptData

    def __init__(
        self,
        router: LLMRouter | None = None,
    ) -> None:
        """Initialize Image Prompt Agent."""
        super().__init__(router=router, name="ImagePromptAgent")

    def get_system_prompt(self) -> str:
        """Get the system prompt for prompt assembly."""
        return image_prompt_prompts.get_system_prompt()

    def get_prompt(self, input_data: ImagePromptInput) -> str:
        """Get the user prompt for prompt assembly."""
        return image_prompt_prompts.get_prompt(
            query=input_data.query,
            year=input_data.year,
            era=input_data.era,
            season=input_data.season,
            time_of_day=input_data.time_of_day,
            location=input_data.location,
            setting=input_data.setting,
            atmosphere=input_data.atmosphere,
            architecture=input_data.architecture,
            lighting=input_data.lighting,
            weather=input_data.weather,
            objects=input_data.objects,
            colors=input_data.colors,
            focal_point=input_data.focal_point,
            character_descriptions=input_data.character_descriptions,
            dialog_context=input_data.dialog_context,
        )

    async def run(self, input_data: ImagePromptInput) -> AgentResult[ImagePromptData]:
        """Assemble the final image generation prompt.

        Args:
            input_data: ImagePromptInput with all context

        Returns:
            AgentResult containing ImagePromptData
        """
        result = await self._call_llm(input_data, temperature=0.6)

        if result.success and result.content:
            result.metadata["prompt_length"] = result.content.prompt_length
            result.metadata["style"] = result.content.style

        return result
