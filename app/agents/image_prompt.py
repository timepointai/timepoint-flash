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

from typing import TYPE_CHECKING

from app.agents.base import AgentResult, BaseAgent
from app.core.historical_validation import validate_historical_scene
from app.core.llm_router import LLMRouter
from app.prompts import image_prompt as image_prompt_prompts
from app.schemas import (
    CameraData,
    CharacterData,
    DialogData,
    ImagePromptData,
    MomentData,
    SceneData,
    TimelineData,
)
from app.schemas.graph import GraphData

if TYPE_CHECKING:
    from app.agents.grounding import GroundedContext


@dataclass
class ImagePromptInput:
    """Input data for Image Prompt Agent.

    Contains ALL data from the pipeline for maximum image quality.
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
    # Additional context from other agents
    relationship_context: str | None = None  # From Graph Agent
    tension_arc: str | None = None  # From Moment Agent
    plot_beat: str | None = None  # From Moment Agent
    camera_shot: str | None = None  # From Camera Agent
    camera_angle: str | None = None  # From Camera Agent
    camera_movement: str | None = None  # From Camera Agent
    composition: str | None = None  # From Camera Agent
    # Grounded context for historical accuracy
    event_mechanics: str | None = None  # How the event physically worked
    visible_technology: str | None = None  # Period-accurate technology description
    photographic_reality: str | None = None  # What a photograph would actually show
    # Physical presence for image generation (critical for showing correct people)
    physical_participants: list[str] = field(default_factory=list)  # People physically visible with positions
    entity_representations: list[str] = field(default_factory=list)  # How to represent non-human entities (format: "Entity: representation")

    @classmethod
    def from_data(
        cls,
        query: str,
        timeline: TimelineData,
        scene: SceneData,
        characters: CharacterData,
        dialog: DialogData | None = None,
        graph: GraphData | None = None,
        moment: MomentData | None = None,
        camera: CameraData | None = None,
        grounded_context: "GroundedContext | None" = None,
    ) -> "ImagePromptInput":
        """Create ImagePromptInput from ALL previous agent data.

        Args:
            query: Original/cleaned query
            timeline: TimelineData from Timeline Agent
            scene: SceneData from Scene Agent
            characters: CharacterData from Characters Agent
            dialog: DialogData from Dialog Agent (optional)
            graph: GraphData from Graph Agent (relationships)
            moment: MomentData from Moment Agent (plot/tension)
            camera: CameraData from Camera Agent (composition)
            grounded_context: GroundedContext from Grounding Agent (historical accuracy)

        Returns:
            ImagePromptInput with all context assembled
        """
        # Build character descriptions
        char_descriptions = [c.to_prompt_description() for c in characters.characters]

        # Build dialog context
        dialog_context = None
        if dialog:
            dialog_context = dialog.to_script()

        # Build relationship context from graph
        relationship_context = None
        if graph and graph.relationships:
            rel_parts = []
            for rel in graph.relationships[:5]:  # Limit to top 5 relationships
                rel_parts.append(f"{rel.from_character} and {rel.to_character}: {rel.relationship_type}")
            relationship_context = "; ".join(rel_parts)

        # Extract moment data
        tension_arc = None
        plot_beat = None
        if moment:
            tension_arc = moment.tension_arc
            if moment.emotional_beats:
                plot_beat = moment.emotional_beats[0] if moment.emotional_beats else None

        # Extract camera data
        camera_shot = None
        camera_angle = None
        camera_movement = None
        composition = None
        if camera:
            camera_shot = camera.shot_type
            camera_angle = camera.angle
            camera_movement = camera.movement
            composition = camera.composition_rule

        # Extract grounded context (critical for historical accuracy)
        event_mechanics = None
        visible_technology = None
        photographic_reality = None
        physical_participants: list[str] = []
        entity_representations: list[str] = []
        if grounded_context:
            event_mechanics = grounded_context.event_mechanics if grounded_context.event_mechanics else None
            visible_technology = grounded_context.visible_technology if grounded_context.visible_technology else None
            photographic_reality = grounded_context.photographic_reality if grounded_context.photographic_reality else None
            # Critical for showing correct people in the image
            physical_participants = grounded_context.physical_participants if grounded_context.physical_participants else []
            entity_representations = grounded_context.entity_representations if grounded_context.entity_representations else {}

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
            relationship_context=relationship_context,
            tension_arc=tension_arc,
            plot_beat=plot_beat,
            camera_shot=camera_shot,
            camera_angle=camera_angle,
            camera_movement=camera_movement,
            composition=composition,
            event_mechanics=event_mechanics,
            visible_technology=visible_technology,
            photographic_reality=photographic_reality,
            physical_participants=physical_participants,
            entity_representations=entity_representations,
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
            event_mechanics=input_data.event_mechanics,
            visible_technology=input_data.visible_technology,
            photographic_reality=input_data.photographic_reality,
            physical_participants=input_data.physical_participants,
            entity_representations=input_data.entity_representations,
        )

    async def run(self, input_data: ImagePromptInput) -> AgentResult[ImagePromptData]:
        """Assemble the final image generation prompt.

        Args:
            input_data: ImagePromptInput with all context

        Returns:
            AgentResult containing ImagePromptData
        """
        # Run historical validation to get era-specific negative prompts
        validation = validate_historical_scene(
            year=input_data.year,
            location=input_data.location,
            query=input_data.query,
        )

        result = await self._call_llm(input_data, temperature=0.6)

        if result.success and result.content:
            # Inject era-specific negative prompts (anachronism prevention)
            result.content.era_negative_prompts = validation.negative_prompts
            result.content.historical_confidence = validation.confidence_score
            result.content.anachronism_warnings = validation.accuracy_warnings
            result.content.distinguishing_guidance = validation.get_distinguishing_guidance()

            # Add metadata
            result.metadata["prompt_length"] = result.content.prompt_length
            result.metadata["style"] = result.content.style
            result.metadata["historical_confidence"] = validation.confidence_score
            result.metadata["era"] = validation.era
            result.metadata["era_negative_count"] = len(validation.negative_prompts)

            # Log warnings if any
            if validation.accuracy_warnings:
                result.metadata["anachronism_warnings"] = validation.accuracy_warnings[:3]

        return result
