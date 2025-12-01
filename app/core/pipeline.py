"""Generation pipeline for timepoint creation.

This module orchestrates the multi-step generation process using agents:
Judge → Timeline → Scene → Characters → Moment → Dialog → Camera → Graph → Image Prompt

Each agent produces structured output that feeds into the next.

Examples:
    >>> from app.core.pipeline import GenerationPipeline
    >>> pipeline = GenerationPipeline()
    >>> result = await pipeline.run("signing of the declaration")
    >>> print(result.slug)
    'signing-of-the-declaration-1776'

Tests:
    - tests/unit/test_pipeline.py::test_pipeline_initialization
    - tests/unit/test_pipeline.py::test_pipeline_step_judge
    - tests/integration/test_pipeline_integration.py::test_full_pipeline
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncGenerator

from app.agents import (
    CameraAgent,
    CharactersAgent,
    DialogAgent,
    GraphAgent,
    ImageGenAgent,
    ImagePromptAgent,
    JudgeAgent,
    MomentAgent,
    SceneAgent,
    TimelineAgent,
)
from app.agents.camera import CameraInput
from app.agents.characters import CharactersInput
from app.agents.dialog import DialogInput
from app.agents.graph import GraphInput
from app.agents.image_gen import ImageGenInput
from app.agents.image_prompt import ImagePromptInput
from app.agents.scene import SceneInput
from app.agents.timeline import TimelineInput
from app.core.llm_router import LLMRouter
from app.models import GenerationLog, Timepoint, TimepointStatus, generate_slug
from app.schemas import (
    CameraData,
    CharacterData,
    DialogData,
    GraphData,
    ImagePromptData,
    JudgeResult,
    MomentData,
    QueryType,
    SceneData,
    TimelineData,
)

logger = logging.getLogger(__name__)


class PipelineStep(str, Enum):
    """Steps in the generation pipeline."""

    JUDGE = "judge"
    TIMELINE = "timeline"
    SCENE = "scene"
    CHARACTERS = "characters"
    MOMENT = "moment"
    DIALOG = "dialog"
    CAMERA = "camera"
    GRAPH = "graph"
    IMAGE_PROMPT = "image_prompt"
    IMAGE_GENERATION = "image_generation"


@dataclass
class StepResult:
    """Result of a single pipeline step.

    Attributes:
        step: The pipeline step
        success: Whether step succeeded
        data: The step output data
        error: Error message if failed
        latency_ms: Step execution time
        model_used: LLM model used
    """

    step: PipelineStep
    success: bool
    data: Any = None
    error: str | None = None
    latency_ms: int = 0
    model_used: str | None = None


@dataclass
class PipelineState:
    """State accumulated during pipeline execution.

    Attributes:
        query: Original query
        judge_result: Result from judge step
        timeline_data: Temporal coordinates
        scene_data: Scene environment
        character_data: Characters
        moment_data: Plot and tension data
        dialog_data: Dialog lines
        camera_data: Camera composition
        graph_data: Character relationships
        image_prompt_data: Assembled prompt
        image_base64: Generated image data
        step_results: Results from each step
        timepoint_id: Generated timepoint ID
    """

    query: str
    judge_result: JudgeResult | None = None
    timeline_data: TimelineData | None = None
    scene_data: SceneData | None = None
    character_data: CharacterData | None = None
    moment_data: MomentData | None = None
    dialog_data: DialogData | None = None
    camera_data: CameraData | None = None
    graph_data: GraphData | None = None
    image_prompt_data: ImagePromptData | None = None
    image_base64: str | None = None
    step_results: list[StepResult] = field(default_factory=list)
    timepoint_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    @property
    def is_valid(self) -> bool:
        """Check if query was validated."""
        return self.judge_result is not None and self.judge_result.is_valid

    @property
    def current_step(self) -> PipelineStep | None:
        """Get the last completed step."""
        if not self.step_results:
            return None
        return self.step_results[-1].step

    @property
    def has_errors(self) -> bool:
        """Check if any step failed."""
        return any(not r.success for r in self.step_results)

    def get_step_result(self, step: PipelineStep) -> StepResult | None:
        """Get result for a specific step."""
        for result in self.step_results:
            if result.step == step:
                return result
        return None


class GenerationPipeline:
    """Orchestrates the multi-step timepoint generation process.

    Uses specialized agents for each step, accumulating state and
    handling errors at each stage.

    Attributes:
        router: LLM router for making API calls

    Examples:
        >>> pipeline = GenerationPipeline()
        >>> result = await pipeline.run("rome 50 BCE")
        >>> print(result.timeline_data.year)
        -50
    """

    def __init__(self, router: LLMRouter | None = None) -> None:
        """Initialize pipeline.

        Args:
            router: LLM router (creates one if not provided)
        """
        self._router = router
        self._agents_initialized = False

        # Agents (lazy initialization)
        self._judge_agent: JudgeAgent | None = None
        self._timeline_agent: TimelineAgent | None = None
        self._scene_agent: SceneAgent | None = None
        self._characters_agent: CharactersAgent | None = None
        self._moment_agent: MomentAgent | None = None
        self._dialog_agent: DialogAgent | None = None
        self._camera_agent: CameraAgent | None = None
        self._graph_agent: GraphAgent | None = None
        self._image_prompt_agent: ImagePromptAgent | None = None
        self._image_gen_agent: ImageGenAgent | None = None

    @property
    def router(self) -> LLMRouter:
        """Get or create LLM router."""
        if self._router is None:
            self._router = LLMRouter()
        return self._router

    def _init_agents(self) -> None:
        """Initialize all agents with the router."""
        if self._agents_initialized:
            return

        router = self.router
        self._judge_agent = JudgeAgent(router=router)
        self._timeline_agent = TimelineAgent(router=router)
        self._scene_agent = SceneAgent(router=router)
        self._characters_agent = CharactersAgent(router=router)
        self._moment_agent = MomentAgent(router=router)
        self._dialog_agent = DialogAgent(router=router)
        self._camera_agent = CameraAgent(router=router)
        self._graph_agent = GraphAgent(router=router)
        self._image_prompt_agent = ImagePromptAgent(router=router)
        self._image_gen_agent = ImageGenAgent(router=router)
        self._agents_initialized = True

    async def run(self, query: str, generate_image: bool = False) -> PipelineState:
        """Run the full generation pipeline.

        Args:
            query: The user's temporal query
            generate_image: Whether to generate the image

        Returns:
            PipelineState with all accumulated data

        Raises:
            ValueError: If query is invalid
        """
        self._init_agents()
        state = PipelineState(query=query)
        logger.info(f"Starting pipeline for query: {query}")

        # Step 1: Judge
        state = await self._step_judge(state)
        if not state.is_valid:
            logger.warning(f"Query invalid: {state.judge_result.reason}")
            return state

        # Step 2: Timeline
        state = await self._step_timeline(state)
        if state.has_errors:
            return state

        # Step 3: Scene
        state = await self._step_scene(state)
        if state.has_errors:
            return state

        # Step 4: Characters
        state = await self._step_characters(state)
        if state.has_errors:
            return state

        # Step 5: Moment
        state = await self._step_moment(state)
        if state.has_errors:
            return state

        # Step 6: Dialog
        state = await self._step_dialog(state)
        if state.has_errors:
            return state

        # Step 7: Camera
        state = await self._step_camera(state)
        if state.has_errors:
            return state

        # Step 8: Graph
        state = await self._step_graph(state)
        if state.has_errors:
            return state

        # Step 9: Image Prompt
        state = await self._step_image_prompt(state)
        if state.has_errors:
            return state

        # Step 10: Image Generation (optional)
        if generate_image:
            state = await self._step_image_generation(state)

        logger.info(f"Pipeline complete for: {query}")
        return state

    async def run_streaming(
        self, query: str, generate_image: bool = False
    ) -> AsyncGenerator[tuple[PipelineStep, StepResult, PipelineState], None]:
        """Run the pipeline with streaming, yielding after each step.

        This method yields a tuple of (step, result, state) after each pipeline
        step completes, enabling real-time progress updates.

        Args:
            query: The user's temporal query
            generate_image: Whether to generate the image

        Yields:
            Tuple of (PipelineStep, StepResult, PipelineState) after each step

        Examples:
            >>> async for step, result, state in pipeline.run_streaming("rome"):
            ...     print(f"{step.value}: {'OK' if result.success else 'FAIL'}")
        """
        self._init_agents()
        state = PipelineState(query=query)
        logger.info(f"Starting streaming pipeline for query: {query}")

        # Step 1: Judge
        state = await self._step_judge(state)
        yield (PipelineStep.JUDGE, state.step_results[-1], state)
        if not state.is_valid:
            logger.warning(f"Query invalid: {state.judge_result.reason}")
            return

        # Step 2: Timeline
        state = await self._step_timeline(state)
        yield (PipelineStep.TIMELINE, state.step_results[-1], state)
        if state.has_errors:
            return

        # Step 3: Scene
        state = await self._step_scene(state)
        yield (PipelineStep.SCENE, state.step_results[-1], state)
        if state.has_errors:
            return

        # Step 4: Characters
        state = await self._step_characters(state)
        yield (PipelineStep.CHARACTERS, state.step_results[-1], state)
        if state.has_errors:
            return

        # Step 5: Moment
        state = await self._step_moment(state)
        yield (PipelineStep.MOMENT, state.step_results[-1], state)
        if state.has_errors:
            return

        # Step 6: Dialog
        state = await self._step_dialog(state)
        yield (PipelineStep.DIALOG, state.step_results[-1], state)
        if state.has_errors:
            return

        # Step 7: Camera
        state = await self._step_camera(state)
        yield (PipelineStep.CAMERA, state.step_results[-1], state)
        if state.has_errors:
            return

        # Step 8: Graph
        state = await self._step_graph(state)
        yield (PipelineStep.GRAPH, state.step_results[-1], state)
        if state.has_errors:
            return

        # Step 9: Image Prompt
        state = await self._step_image_prompt(state)
        yield (PipelineStep.IMAGE_PROMPT, state.step_results[-1], state)
        if state.has_errors:
            return

        # Step 10: Image Generation (optional)
        if generate_image:
            state = await self._step_image_generation(state)
            yield (PipelineStep.IMAGE_GENERATION, state.step_results[-1], state)

        logger.info(f"Streaming pipeline complete for: {query}")

    async def _step_judge(self, state: PipelineState) -> PipelineState:
        """Execute the judge step using JudgeAgent."""
        step = PipelineStep.JUDGE

        result = await self._judge_agent.run(state.query)

        if result.success:
            state.judge_result = result.content
        else:
            # Create a failed judge result
            state.judge_result = JudgeAgent.create_failed_result(result.error)

        state.step_results.append(
            StepResult(
                step=step,
                success=result.success,
                data=state.judge_result,
                error=result.error,
                latency_ms=result.latency_ms,
                model_used=result.model_used,
            )
        )

        logger.debug(f"Judge: valid={state.judge_result.is_valid}")
        return state

    async def _step_timeline(self, state: PipelineState) -> PipelineState:
        """Execute the timeline step using TimelineAgent."""
        step = PipelineStep.TIMELINE

        input_data = TimelineInput.from_judge_result(state.query, state.judge_result)
        result = await self._timeline_agent.run(input_data)

        if result.success:
            state.timeline_data = result.content

        state.step_results.append(
            StepResult(
                step=step,
                success=result.success,
                data=state.timeline_data,
                error=result.error,
                latency_ms=result.latency_ms,
                model_used=result.model_used,
            )
        )

        if state.timeline_data:
            logger.debug(f"Timeline: {state.timeline_data.year} at {state.timeline_data.location}")
        return state

    async def _step_scene(self, state: PipelineState) -> PipelineState:
        """Execute the scene step using SceneAgent."""
        step = PipelineStep.SCENE

        if not state.timeline_data:
            state.step_results.append(
                StepResult(
                    step=step,
                    success=False,
                    error="Timeline data required for scene generation",
                )
            )
            return state

        input_data = SceneInput.from_timeline(
            state.judge_result.cleaned_query or state.query,
            state.timeline_data,
        )
        result = await self._scene_agent.run(input_data)

        if result.success:
            state.scene_data = result.content

        state.step_results.append(
            StepResult(
                step=step,
                success=result.success,
                data=state.scene_data,
                error=result.error,
                latency_ms=result.latency_ms,
                model_used=result.model_used,
            )
        )

        if state.scene_data:
            logger.debug(f"Scene: {state.scene_data.setting[:50]}...")
        return state

    async def _step_characters(self, state: PipelineState) -> PipelineState:
        """Execute the characters step using CharactersAgent."""
        step = PipelineStep.CHARACTERS

        if not state.timeline_data or not state.scene_data:
            state.step_results.append(
                StepResult(
                    step=step,
                    success=False,
                    error="Timeline and scene data required for characters",
                )
            )
            return state

        input_data = CharactersInput.from_data(
            query=state.judge_result.cleaned_query or state.query,
            timeline=state.timeline_data,
            scene=state.scene_data,
            detected_figures=state.judge_result.detected_figures,
        )
        result = await self._characters_agent.run(input_data)

        if result.success:
            state.character_data = result.content

        state.step_results.append(
            StepResult(
                step=step,
                success=result.success,
                data=state.character_data,
                error=result.error,
                latency_ms=result.latency_ms,
                model_used=result.model_used,
            )
        )

        if state.character_data:
            logger.debug(f"Characters: {len(state.character_data.characters)} created")
        return state

    async def _step_moment(self, state: PipelineState) -> PipelineState:
        """Execute the moment step using MomentAgent."""
        step = PipelineStep.MOMENT

        if not all([state.timeline_data, state.scene_data, state.character_data]):
            state.step_results.append(
                StepResult(
                    step=step,
                    success=False,
                    error="Timeline, scene, and character data required for moment",
                )
            )
            return state

        from app.agents.moment import MomentInput

        input_data = MomentInput(
            query=state.judge_result.cleaned_query or state.query,
            year=state.timeline_data.year,
            era=state.timeline_data.era,
            location=state.timeline_data.location,
            setting=state.scene_data.setting,
            atmosphere=state.scene_data.atmosphere,
            characters=[c.name for c in state.character_data.characters],
        )
        result = await self._moment_agent.run(input_data)

        if result.success:
            state.moment_data = result.content

        state.step_results.append(
            StepResult(
                step=step,
                success=result.success,
                data=state.moment_data,
                error=result.error,
                latency_ms=result.latency_ms,
                model_used=result.model_used,
            )
        )

        if state.moment_data:
            logger.debug(f"Moment: tension_arc={state.moment_data.tension_arc}")
        return state

    async def _step_dialog(self, state: PipelineState) -> PipelineState:
        """Execute the dialog step using DialogAgent."""
        step = PipelineStep.DIALOG

        if not all([state.timeline_data, state.scene_data, state.character_data]):
            state.step_results.append(
                StepResult(
                    step=step,
                    success=False,
                    error="Timeline, scene, and character data required for dialog",
                )
            )
            return state

        input_data = DialogInput.from_data(
            query=state.judge_result.cleaned_query or state.query,
            timeline=state.timeline_data,
            scene=state.scene_data,
            characters=state.character_data,
        )
        result = await self._dialog_agent.run(input_data)

        if result.success:
            state.dialog_data = result.content

        state.step_results.append(
            StepResult(
                step=step,
                success=result.success,
                data=state.dialog_data,
                error=result.error,
                latency_ms=result.latency_ms,
                model_used=result.model_used,
            )
        )

        if state.dialog_data:
            logger.debug(f"Dialog: {len(state.dialog_data.lines)} lines")
        return state

    async def _step_camera(self, state: PipelineState) -> PipelineState:
        """Execute the camera step using CameraAgent."""
        step = PipelineStep.CAMERA

        if not all([state.scene_data]):
            state.step_results.append(
                StepResult(
                    step=step,
                    success=False,
                    error="Scene data required for camera composition",
                )
            )
            return state

        input_data = CameraInput(
            query=state.judge_result.cleaned_query or state.query,
            setting=state.scene_data.setting,
            atmosphere=state.scene_data.atmosphere,
            tension_level=state.scene_data.tension_level or "medium",
            focal_point=state.scene_data.focal_point,
        )
        result = await self._camera_agent.run(input_data)

        if result.success:
            state.camera_data = result.content

        state.step_results.append(
            StepResult(
                step=step,
                success=result.success,
                data=state.camera_data,
                error=result.error,
                latency_ms=result.latency_ms,
                model_used=result.model_used,
            )
        )

        if state.camera_data:
            logger.debug(f"Camera: {state.camera_data.shot_type}, {state.camera_data.angle}")
        return state

    async def _step_graph(self, state: PipelineState) -> PipelineState:
        """Execute the graph step using GraphAgent."""
        step = PipelineStep.GRAPH

        if not all([state.timeline_data, state.character_data]):
            state.step_results.append(
                StepResult(
                    step=step,
                    success=False,
                    error="Timeline and character data required for graph",
                )
            )
            return state

        input_data = GraphInput(
            query=state.judge_result.cleaned_query or state.query,
            year=state.timeline_data.year,
            era=state.timeline_data.era,
            location=state.timeline_data.location,
            characters=[
                {"name": c.name, "role": c.role.value}
                for c in state.character_data.characters
            ],
        )
        result = await self._graph_agent.run(input_data)

        if result.success:
            state.graph_data = result.content

        state.step_results.append(
            StepResult(
                step=step,
                success=result.success,
                data=state.graph_data,
                error=result.error,
                latency_ms=result.latency_ms,
                model_used=result.model_used,
            )
        )

        if state.graph_data:
            logger.debug(f"Graph: {len(state.graph_data.relationships)} relationships")
        return state

    async def _step_image_prompt(self, state: PipelineState) -> PipelineState:
        """Execute the image prompt step using ImagePromptAgent."""
        step = PipelineStep.IMAGE_PROMPT

        if not all([state.timeline_data, state.scene_data, state.character_data]):
            state.step_results.append(
                StepResult(
                    step=step,
                    success=False,
                    error="Timeline, scene, and character data required",
                )
            )
            return state

        input_data = ImagePromptInput.from_data(
            query=state.judge_result.cleaned_query or state.query,
            timeline=state.timeline_data,
            scene=state.scene_data,
            characters=state.character_data,
            dialog=state.dialog_data,
        )
        result = await self._image_prompt_agent.run(input_data)

        if result.success:
            state.image_prompt_data = result.content

        state.step_results.append(
            StepResult(
                step=step,
                success=result.success,
                data=state.image_prompt_data,
                error=result.error,
                latency_ms=result.latency_ms,
                model_used=result.model_used,
            )
        )

        if state.image_prompt_data:
            logger.debug(f"Image prompt: {state.image_prompt_data.prompt_length} chars")
        return state

    async def _step_image_generation(self, state: PipelineState) -> PipelineState:
        """Execute image generation using ImageGenAgent."""
        step = PipelineStep.IMAGE_GENERATION

        if not state.image_prompt_data:
            state.step_results.append(
                StepResult(
                    step=step,
                    success=False,
                    error="Image prompt required for generation",
                )
            )
            return state

        input_data = ImageGenInput(
            prompt=state.image_prompt_data.full_prompt,
            style=state.image_prompt_data.style,
            aspect_ratio=state.image_prompt_data.aspect_ratio,
        )
        result = await self._image_gen_agent.run(input_data)

        if result.success:
            state.image_base64 = result.content.image_base64

        state.step_results.append(
            StepResult(
                step=step,
                success=result.success,
                data={"image_generated": result.success} if result.success else None,
                error=result.error,
                latency_ms=result.latency_ms,
                model_used=result.model_used,
            )
        )

        if result.success:
            logger.debug("Image generation: complete")
        return state

    def state_to_timepoint(self, state: PipelineState) -> Timepoint:
        """Convert pipeline state to Timepoint model.

        Args:
            state: Completed pipeline state

        Returns:
            Timepoint model ready for database
        """
        # Determine status
        if not state.is_valid:
            status = TimepointStatus.FAILED
        elif state.has_errors:
            status = TimepointStatus.FAILED
        else:
            status = TimepointStatus.COMPLETED

        # Generate slug
        year = state.timeline_data.year if state.timeline_data else None
        slug = generate_slug(state.query, year)

        # Build timepoint
        timepoint = Timepoint(
            id=state.timepoint_id,
            query=state.query,
            slug=slug,
            status=status,
        )

        # Add timeline data
        if state.timeline_data:
            timepoint.year = state.timeline_data.year
            timepoint.month = state.timeline_data.month
            timepoint.day = state.timeline_data.day
            timepoint.season = state.timeline_data.season
            timepoint.time_of_day = state.timeline_data.time_of_day
            timepoint.era = state.timeline_data.era
            timepoint.location = state.timeline_data.location

        # Add metadata JSON
        if state.timeline_data:
            timepoint.metadata_json = {
                "timeline": state.timeline_data.model_dump(),
            }
            if state.scene_data:
                timepoint.metadata_json["scene"] = state.scene_data.model_dump()
            if state.moment_data:
                timepoint.metadata_json["moment"] = state.moment_data.model_dump()
            if state.camera_data:
                timepoint.metadata_json["camera"] = state.camera_data.model_dump()
            if state.graph_data:
                timepoint.metadata_json["graph"] = state.graph_data.model_dump()

        # Add character data
        if state.character_data:
            timepoint.character_data_json = state.character_data.model_dump()

        # Add scene data
        if state.scene_data:
            timepoint.scene_data_json = state.scene_data.model_dump()

        # Add dialog
        if state.dialog_data:
            timepoint.dialog_json = [
                line.model_dump() for line in state.dialog_data.lines
            ]

        # Add image prompt
        if state.image_prompt_data:
            timepoint.image_prompt = state.image_prompt_data.full_prompt

        # Add image data
        if state.image_base64:
            timepoint.image_base64 = state.image_base64

        # Add error if failed
        if status == TimepointStatus.FAILED:
            errors = [r.error for r in state.step_results if r.error]
            timepoint.error_message = "; ".join(errors) if errors else "Unknown error"

        return timepoint

    def state_to_generation_logs(self, state: PipelineState) -> list[GenerationLog]:
        """Convert step results to generation logs.

        Args:
            state: Completed pipeline state

        Returns:
            List of GenerationLog models
        """
        logs = []
        for result in state.step_results:
            log = GenerationLog(
                timepoint_id=state.timepoint_id,
                step=result.step.value,
                status="success" if result.success else "failed",
                input_data={"query": state.query},
                output_data=result.data.model_dump() if hasattr(result.data, "model_dump") else None,
                model_used=result.model_used,
                latency_ms=result.latency_ms,
                error_message=result.error,
            )
            logs.append(log)
        return logs
