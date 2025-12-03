"""Generation pipeline for timepoint creation.

This module orchestrates the multi-step generation process using agents:
Judge → Timeline → Scene → Characters (ID→Graph→Bios) → Moment+Camera → Dialog → Image Prompt

The character step now runs Graph generation BEFORE character bios, so relationship
context informs each character's portrayal. Each agent produces structured output
that feeds into the next.

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

import asyncio
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
from app.agents.character_bio import CharacterBioAgent, CharacterBioInput, create_fallback_character
from app.agents.character_identification import CharacterIdentificationAgent, CharacterIdentificationInput
from app.agents.camera import CameraInput
from app.agents.characters import CharactersInput
from app.agents.dialog import DialogInput
from app.agents.graph import GraphInput
from app.agents.image_gen import ImageGenInput
from app.agents.image_prompt import ImagePromptInput
from app.agents.scene import SceneInput
from app.agents.timeline import TimelineInput
from app.config import ParallelismMode, QualityPreset, get_preset_parallelism
from app.core.llm_router import LLMRouter, ModelTier, TIER_PARALLELISM
from app.models import GenerationLog, Timepoint, TimepointStatus, generate_slug
from app.schemas import (
    CameraData,
    Character,
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
from app.schemas.character_identification import CharacterIdentification

logger = logging.getLogger(__name__)


class PipelineStep(str, Enum):
    """Steps in the generation pipeline.

    Order is important for data flow:
    1. Judge - Validate query
    2. Timeline - Temporal coordinates
    3. Scene - Environment
    4. Characters - Who's there
    5. Graph - Character relationships (needed for dialog!)
    6. Moment - Plot/tension arc
    7. Dialog - Informed by relationships & tension
    8. Camera - Composition
    9. ImagePrompt - Uses ALL data (graph, moment, camera)
    10. ImageGeneration - Final image
    """

    JUDGE = "judge"
    TIMELINE = "timeline"
    SCENE = "scene"
    CHARACTERS = "characters"
    GRAPH = "graph"  # Moved up: relationships inform dialog
    MOMENT = "moment"
    DIALOG = "dialog"
    CAMERA = "camera"
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
        preset: Quality preset (HD, HYPER, BALANCED)
        text_model: Custom text model override
        image_model: Custom image model override

    Examples:
        >>> pipeline = GenerationPipeline()
        >>> result = await pipeline.run("rome 50 BCE")
        >>> print(result.timeline_data.year)
        -50

        >>> # With preset for fast generation
        >>> pipeline = GenerationPipeline(preset=QualityPreset.HYPER)
        >>> result = await pipeline.run("rome 50 BCE")

        >>> # With custom models (overrides preset)
        >>> pipeline = GenerationPipeline(
        ...     text_model="google/gemini-2.0-flash-001",
        ...     image_model="black-forest-labs/flux-1.1-pro"
        ... )
    """

    def __init__(
        self,
        router: LLMRouter | None = None,
        preset: QualityPreset | None = None,
        text_model: str | None = None,
        image_model: str | None = None,
        max_parallelism: int | None = None,
    ) -> None:
        """Initialize pipeline.

        Args:
            router: LLM router (creates one if not provided)
            preset: Quality preset (HD, HYPER, BALANCED)
            text_model: Custom text model override (overrides preset)
            image_model: Custom image model override (overrides preset)
            max_parallelism: Maximum parallel LLM calls (default from settings)
        """
        from app.config import settings

        self._router = router
        self._preset = preset
        self._text_model = text_model
        self._image_model = image_model
        self._max_parallelism_override = max_parallelism
        self._max_parallelism: int | None = None  # Set during execution planning
        self._semaphore: asyncio.Semaphore | None = None
        self._agents_initialized = False
        self._model_tier: ModelTier | None = None  # Cached model tier
        self._parallelism_mode: ParallelismMode | None = None  # Cached parallelism mode

        # Agents (lazy initialization)
        self._judge_agent: JudgeAgent | None = None
        self._timeline_agent: TimelineAgent | None = None
        self._scene_agent: SceneAgent | None = None
        self._characters_agent: CharactersAgent | None = None
        self._char_id_agent: CharacterIdentificationAgent | None = None
        self._char_bio_agent: CharacterBioAgent | None = None
        self._moment_agent: MomentAgent | None = None
        self._dialog_agent: DialogAgent | None = None
        self._camera_agent: CameraAgent | None = None
        self._graph_agent: GraphAgent | None = None
        self._image_prompt_agent: ImagePromptAgent | None = None
        self._image_gen_agent: ImageGenAgent | None = None

    @property
    def router(self) -> LLMRouter:
        """Get or create LLM router (with preset and/or custom models)."""
        if self._router is None:
            self._router = LLMRouter(
                preset=self._preset,
                text_model=self._text_model,
                image_model=self._image_model,
            )
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
        self._char_id_agent = CharacterIdentificationAgent(router=router)
        self._char_bio_agent = CharacterBioAgent(router=router)
        self._moment_agent = MomentAgent(router=router)
        self._dialog_agent = DialogAgent(router=router)
        self._camera_agent = CameraAgent(router=router)
        self._graph_agent = GraphAgent(router=router)
        self._image_prompt_agent = ImagePromptAgent(router=router)
        self._image_gen_agent = ImageGenAgent(router=router)
        self._agents_initialized = True

    def _plan_execution(self) -> None:
        """Plan execution strategy based on model tier and parallelism mode.

        Determines parallelism level and execution strategy based on the
        model's tier classification and quality preset. This proactively
        prevents rate limit errors instead of relying on reactive retry.

        Execution strategies by tier and mode:
        - FREE tier: Sequential execution (parallelism=1-2)
        - PAID tier: Moderate parallelism (2-5 based on mode)
        - NATIVE tier: High parallelism (3-8 based on mode)

        Parallelism modes:
        - SEQUENTIAL: 1 call at a time (safest)
        - NORMAL: Tier-based default (1-3 concurrent)
        - AGGRESSIVE: Higher parallelism (2-5 concurrent)
        - MAX: Maximum safe parallelism (provider limit - 1, up to 8)

        Side effects:
            - Sets self._model_tier
            - Sets self._parallelism_mode
            - Sets self._max_parallelism
            - Creates self._semaphore
        """
        # Get model tier and parallelism mode from router
        self._model_tier = self.router.get_model_tier()
        self._parallelism_mode = self.router.get_parallelism_mode()

        # Determine parallelism: override > effective max (tier + mode + provider)
        if self._max_parallelism_override:
            self._max_parallelism = self._max_parallelism_override
        else:
            self._max_parallelism = self.router.get_effective_max_concurrent()

        # Create semaphore for controlled parallelism
        self._semaphore = asyncio.Semaphore(self._max_parallelism)

        logger.info(
            f"Execution plan: tier={self._model_tier.value}, "
            f"mode={self._parallelism_mode.value}, "
            f"parallelism={self._max_parallelism}, "
            f"optimized_flow={self.use_optimized_flow}"
        )

    @property
    def model_tier(self) -> ModelTier:
        """Get the current model tier (plans execution if not already planned)."""
        if self._model_tier is None:
            self._plan_execution()
        return self._model_tier

    @property
    def parallelism_mode(self) -> ParallelismMode:
        """Get the current parallelism mode (plans execution if not already planned)."""
        if self._parallelism_mode is None:
            self._plan_execution()
        return self._parallelism_mode

    @property
    def use_parallel_characters(self) -> bool:
        """Whether to use parallel character bio generation.

        FREE tier uses single-call to avoid rate limits.
        PAID and NATIVE tiers use parallel bio generation.
        """
        return self.model_tier != ModelTier.FREE

    @property
    def use_optimized_flow(self) -> bool:
        """Whether to use optimized parallel execution flow.

        AGGRESSIVE and MAX modes use optimized flow where:
        - Camera starts immediately after Scene (doesn't wait for Characters)
        - Moment can start after CharacterID (doesn't wait for full bios)

        This maximizes parallelism while maintaining data flow integrity.
        """
        return self.parallelism_mode in (ParallelismMode.AGGRESSIVE, ParallelismMode.MAX)

    async def run(self, query: str, generate_image: bool = False) -> PipelineState:
        """Run the full generation pipeline with mode-aware parallel execution.

        Execution flow depends on parallelism mode:

        SEQUENTIAL/NORMAL mode (standard flow):
        - Sequential: Judge → Timeline → Scene → Characters (with Graph)
        - Parallel: Moment + Camera (after Characters)
        - Sequential: Dialog → ImagePrompt → ImageGen

        AGGRESSIVE/MAX mode (optimized flow):
        - Sequential: Judge → Timeline → Scene
        - Parallel: Camera starts immediately after Scene
        - Characters: CharacterID → (Graph + Moment + Bios in parallel)
        - Sequential: Dialog → ImagePrompt → ImageGen

        Args:
            query: The user's temporal query
            generate_image: Whether to generate the image

        Returns:
            PipelineState with all accumulated data

        Raises:
            ValueError: If query is invalid
        """
        self._init_agents()
        self._plan_execution()  # Determine tier-based parallelism
        state = PipelineState(query=query)
        logger.info(
            f"Starting pipeline for query: {query} "
            f"(tier={self._model_tier.value}, mode={self._parallelism_mode.value}, "
            f"parallelism={self._max_parallelism})"
        )

        # === SEQUENTIAL PHASE 1: Foundation steps ===
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

        # === MODE-DEPENDENT EXECUTION ===
        if self.use_optimized_flow:
            # AGGRESSIVE/MAX: Camera can start immediately after Scene
            state = await self._run_optimized_flow(state)
        else:
            # SEQUENTIAL/NORMAL: Standard flow
            state = await self._run_standard_flow(state)

        if state.has_errors:
            logger.warning("Errors in character/parallel phase, continuing with available data")

        # === SEQUENTIAL PHASE 2: Steps that need parallel results ===
        # Step 7: Dialog (needs Graph for relationships + Moment for tension)
        state = await self._step_dialog(state)
        if state.has_errors:
            logger.warning("Dialog step had errors, continuing")

        # Step 9: Image Prompt (uses ALL data)
        state = await self._step_image_prompt(state)
        if state.has_errors:
            logger.warning("Image prompt step had errors")
            if generate_image:
                return state

        # Step 10: Image Generation (optional)
        if generate_image:
            state = await self._step_image_generation(state)

        logger.info(f"Pipeline complete for: {query}")
        return state

    async def _run_standard_flow(self, state: PipelineState) -> PipelineState:
        """Run standard execution flow (SEQUENTIAL/NORMAL modes).

        Flow: Characters (with Graph) → Moment + Camera in parallel
        """
        # Step 4: Characters (includes Graph generation)
        state = await self._step_characters(state)
        if state.has_errors:
            return state

        # Parallel: Moment + Camera (Graph already done in characters step)
        logger.debug("Starting parallel phase: Moment + Camera")

        async def run_with_semaphore(coro):
            async with self._semaphore:
                return await coro

        moment_task = run_with_semaphore(self._step_moment(state))
        camera_task = run_with_semaphore(self._step_camera(state))

        parallel_results = await asyncio.gather(
            moment_task, camera_task,
            return_exceptions=True
        )

        # Merge parallel results
        self._merge_parallel_results(state, parallel_results, ["moment", "camera"])
        return state

    async def _run_optimized_flow(self, state: PipelineState) -> PipelineState:
        """Run optimized execution flow (AGGRESSIVE/MAX modes).

        Flow: Scene triggers Camera immediately, while Characters runs in parallel.
        Camera only needs Scene data, so it can start without waiting for Characters.

        Optimized parallelism:
        - Camera starts immediately after Scene
        - CharacterID → then Graph + Moment + BioGeneration in parallel
        """
        import time
        logger.debug("Starting optimized flow: Camera parallel with Characters")

        async def run_with_semaphore(coro):
            async with self._semaphore:
                return await coro

        # Start Camera immediately (only needs Scene data)
        camera_task = asyncio.create_task(run_with_semaphore(self._step_camera(state)))

        # Run Characters step (which internally does CharacterID → Graph → Bios)
        # For optimized flow with parallel bios, see _step_characters_optimized
        if self.use_parallel_characters:
            state = await self._step_characters_optimized(state)
        else:
            state = await self._step_characters_fallback(state)

        if state.has_errors:
            # Still wait for Camera to complete
            try:
                camera_result = await camera_task
                if isinstance(camera_result, PipelineState) and camera_result.camera_data:
                    state.camera_data = camera_result.camera_data
                    state.step_results.extend([
                        r for r in camera_result.step_results
                        if r.step == PipelineStep.CAMERA
                    ])
            except Exception as e:
                logger.error(f"Camera step failed: {e}")
            return state

        # Wait for Camera if not done yet
        try:
            camera_result = await camera_task
            if isinstance(camera_result, PipelineState) and camera_result.camera_data:
                state.camera_data = camera_result.camera_data
                state.step_results.extend([
                    r for r in camera_result.step_results
                    if r.step == PipelineStep.CAMERA
                ])
        except Exception as e:
            logger.error(f"Camera step failed: {e}")
            state.step_results.append(
                StepResult(step=PipelineStep.CAMERA, success=False, error=str(e))
            )

        # Moment step (if not already done in optimized characters)
        if not state.moment_data:
            state = await self._step_moment(state)

        return state

    async def _step_characters_optimized(self, state: PipelineState) -> PipelineState:
        """Optimized character generation for AGGRESSIVE/MAX modes.

        Runs Graph + Moment + BioGeneration in parallel after CharacterID.
        Moment only needs character names, not full bios, so it can run earlier.
        """
        step = PipelineStep.CHARACTERS
        import time

        if not state.timeline_data or not state.scene_data:
            state.step_results.append(
                StepResult(
                    step=step,
                    success=False,
                    error="Timeline and scene data required for characters",
                )
            )
            return state

        start_time = time.time()
        query = state.judge_result.cleaned_query or state.query

        # === PHASE 1: Character Identification (fast) ===
        logger.debug("Optimized Characters Phase 1: Identification")
        id_input = CharacterIdentificationInput.from_data(
            query=query,
            timeline=state.timeline_data,
            scene=state.scene_data,
            detected_figures=state.judge_result.detected_figures,
        )
        id_result = await self._char_id_agent.run(id_input)

        if not id_result.success or not id_result.content:
            logger.warning("Character identification failed, falling back to single-call")
            return await self._step_characters_fallback(state)

        char_identification: CharacterIdentification = id_result.content
        character_names = [stub.name for stub in char_identification.characters]
        logger.debug(f"Identified {len(character_names)} characters: {character_names}")

        # === PHASE 2: Parallel Graph + Moment + Bio Generation ===
        # Key optimization: Moment only needs character names, not full bios!
        logger.debug("Optimized Characters Phase 2: Graph + Moment + Bios in parallel")

        async def run_with_semaphore(coro):
            async with self._semaphore:
                return await coro

        # Prepare Graph input
        graph_input = GraphInput(
            query=query,
            year=state.timeline_data.year,
            era=state.timeline_data.era,
            location=state.timeline_data.location,
            characters=[
                {"name": stub.name, "role": stub.role.value}
                for stub in char_identification.characters
            ],
        )

        # Prepare Moment input (uses character names only!)
        from app.agents.moment import MomentInput
        moment_input = MomentInput(
            query=query,
            year=state.timeline_data.year,
            era=state.timeline_data.era,
            location=state.timeline_data.location,
            setting=state.scene_data.setting,
            atmosphere=state.scene_data.atmosphere,
            characters=character_names,  # Just names, not full bios
        )

        # Start Graph and Moment in parallel
        graph_task = asyncio.create_task(run_with_semaphore(self._graph_agent.run(graph_input)))
        moment_task = asyncio.create_task(run_with_semaphore(self._moment_agent.run(moment_input)))

        # Wait for Graph first (needed for bio generation)
        graph_result = await graph_task
        graph_data: GraphData | None = None
        if graph_result.success and graph_result.content:
            graph_data = graph_result.content
            state.graph_data = graph_data
            logger.debug(f"Graph: {len(graph_data.relationships)} relationships")

        # Generate bios in parallel (now that we have graph data)
        async def generate_bio(stub):
            async with self._semaphore:
                bio_input = CharacterBioInput.from_identification(
                    stub=stub,
                    full_cast=char_identification,
                    query=query,
                    year=state.timeline_data.year,
                    era=state.timeline_data.era,
                    location=state.timeline_data.location,
                    setting=state.scene_data.setting,
                    atmosphere=state.scene_data.atmosphere,
                    tension_level=state.scene_data.tension_level or "medium",
                    graph_data=graph_data,
                )
                return await self._char_bio_agent.run(bio_input)

        bio_tasks = [generate_bio(stub) for stub in char_identification.characters]
        bio_results = await asyncio.gather(*bio_tasks, return_exceptions=True)

        # Wait for Moment
        moment_result = await moment_task
        if moment_result.success and moment_result.content:
            state.moment_data = moment_result.content
            state.step_results.append(
                StepResult(
                    step=PipelineStep.MOMENT,
                    success=True,
                    data=state.moment_data,
                    latency_ms=moment_result.latency_ms,
                    model_used=moment_result.model_used,
                )
            )
            logger.debug(f"Moment: tension_arc={state.moment_data.tension_arc}")

        # Assemble characters from bio results
        characters: list[Character] = []
        total_latency = id_result.latency_ms
        if graph_result:
            total_latency += graph_result.latency_ms
        models_used = [id_result.model_used] if id_result.model_used else []

        for i, result in enumerate(bio_results):
            stub = char_identification.characters[i]
            if isinstance(result, Exception):
                logger.warning(f"Bio generation failed for {stub.name}: {result}")
                characters.append(create_fallback_character(stub))
            elif result.success and result.content:
                characters.append(result.content)
                total_latency += result.latency_ms
                if result.model_used and result.model_used not in models_used:
                    models_used.append(result.model_used)
            else:
                characters.append(create_fallback_character(stub))

        # Build CharacterData
        state.character_data = CharacterData(
            characters=characters,
            focal_character=char_identification.focal_character,
            group_dynamics=char_identification.group_dynamics,
            historical_accuracy_note=char_identification.historical_accuracy_note,
        )

        elapsed_ms = int((time.time() - start_time) * 1000)
        state.step_results.append(
            StepResult(
                step=step,
                success=True,
                data=state.character_data,
                latency_ms=elapsed_ms,
                model_used=", ".join(models_used) if models_used else None,
            )
        )

        logger.debug(f"Optimized Characters: {len(characters)} created in {elapsed_ms}ms (parallel Graph+Moment+Bios)")
        return state

    def _merge_parallel_results(
        self,
        state: PipelineState,
        results: list,
        step_names: list[str],
    ) -> None:
        """Merge results from parallel execution back into state."""
        for i, result in enumerate(results):
            step_name = step_names[i]
            if isinstance(result, Exception):
                logger.error(f"Parallel step {step_name} failed: {result}")
                state.step_results.append(
                    StepResult(
                        step=PipelineStep[step_name.upper()],
                        success=False,
                        error=str(result),
                    )
                )
            elif isinstance(result, PipelineState):
                if step_name == "moment" and result.moment_data:
                    state.moment_data = result.moment_data
                    state.step_results.extend([
                        r for r in result.step_results
                        if r.step == PipelineStep.MOMENT
                    ])
                elif step_name == "camera" and result.camera_data:
                    state.camera_data = result.camera_data
                    state.step_results.extend([
                        r for r in result.step_results
                        if r.step == PipelineStep.CAMERA
                    ])

    async def run_streaming(
        self, query: str, generate_image: bool = False
    ) -> AsyncGenerator[tuple[PipelineStep, StepResult, PipelineState], None]:
        """Run the pipeline with streaming and parallel execution.

        Executes independent steps in parallel and yields results as they complete:
        - Sequential: Judge → Timeline → Scene → Characters (yielded immediately)
        - Parallel: Graph + Moment + Camera (yielded as each completes)
        - Sequential: Dialog → ImagePrompt → ImageGen (yielded immediately)

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
        self._plan_execution()  # Determine tier-based parallelism
        state = PipelineState(query=query)
        logger.info(f"Starting streaming pipeline for query: {query} (tier={self._model_tier.value}, parallelism={self._max_parallelism})")

        # === SEQUENTIAL PHASE 1: Foundation steps ===
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

        # === PARALLEL PHASE: Independent analysis steps ===
        # Note: Graph is now generated inside _step_characters() to inform bios
        # Moment and Camera can run in parallel (they don't depend on each other)
        logger.debug("Starting parallel streaming phase: Moment + Camera")

        async def run_with_semaphore_and_name(coro, step_name: str):
            """Run a coroutine with semaphore and return (name, result)."""
            async with self._semaphore:
                result = await coro
                return (step_name, result)

        # Create tasks for parallel execution (Graph already done in characters step)
        tasks = [
            asyncio.create_task(run_with_semaphore_and_name(self._step_moment(state), "moment")),
            asyncio.create_task(run_with_semaphore_and_name(self._step_camera(state), "camera")),
        ]

        # Yield results as each parallel task completes
        for completed_task in asyncio.as_completed(tasks):
            try:
                step_name, result_state = await completed_task

                if isinstance(result_state, PipelineState):
                    # Merge result into main state and yield
                    if step_name == "moment":
                        state.moment_data = result_state.moment_data
                        step_result = [r for r in result_state.step_results if r.step == PipelineStep.MOMENT]
                        if step_result:
                            state.step_results.append(step_result[0])
                            yield (PipelineStep.MOMENT, step_result[0], state)
                    elif step_name == "camera":
                        state.camera_data = result_state.camera_data
                        step_result = [r for r in result_state.step_results if r.step == PipelineStep.CAMERA]
                        if step_result:
                            state.step_results.append(step_result[0])
                            yield (PipelineStep.CAMERA, step_result[0], state)

            except Exception as e:
                logger.error(f"Parallel task failed: {e}")
                # Create error result for failed task
                error_result = StepResult(
                    step=PipelineStep.MOMENT,  # Default step for error
                    success=False,
                    error=str(e),
                )
                state.step_results.append(error_result)

        # Check for errors in parallel phase (don't fail, continue with available data)
        if state.has_errors:
            logger.warning("Errors in parallel phase, continuing with available data")

        # === SEQUENTIAL PHASE 2: Steps that need parallel results ===
        # Step 7: Dialog (needs Graph for relationships + Moment for tension)
        state = await self._step_dialog(state)
        yield (PipelineStep.DIALOG, state.step_results[-1], state)
        if state.has_errors:
            logger.warning("Dialog step had errors, continuing")

        # Step 9: Image Prompt (uses ALL data)
        state = await self._step_image_prompt(state)
        yield (PipelineStep.IMAGE_PROMPT, state.step_results[-1], state)
        if state.has_errors:
            logger.warning(f"Pipeline has errors after image_prompt, skipping image generation")
            return

        # Step 10: Image Generation (optional)
        logger.info(f"Image generation check: generate_image={generate_image}")
        if generate_image:
            logger.info("Running image generation step...")
            state = await self._step_image_generation(state)
            yield (PipelineStep.IMAGE_GENERATION, state.step_results[-1], state)
        else:
            logger.info("Skipping image generation (not requested)")

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
        """Execute character generation with tier-aware strategy.

        Execution strategy based on model tier:
        - FREE tier: Single-call fallback (avoids rate limits)
        - PAID/NATIVE tier: Three-phase generation with graph-informed bios
          1. CharacterIdentificationAgent - Fast identification
          2. GraphAgent - Generate relationships from character stubs
          3. CharacterBioAgent (parallel) - Detailed bio with relationship context

        The graph step is integrated here to inform character bios with relationship
        dynamics, improving character consistency and interaction portrayal.
        """
        step = PipelineStep.CHARACTERS
        import time

        if not state.timeline_data or not state.scene_data:
            state.step_results.append(
                StepResult(
                    step=step,
                    success=False,
                    error="Timeline and scene data required for characters",
                )
            )
            return state

        # FREE tier: Use single-call to avoid rate limits
        if not self.use_parallel_characters:
            logger.info("Using single-call character generation (FREE tier)")
            return await self._step_characters_fallback(state)

        start_time = time.time()
        query = state.judge_result.cleaned_query or state.query

        # === PHASE 1: Character Identification (fast) ===
        logger.debug("Characters Phase 1: Identification (PAID/NATIVE tier)")
        id_input = CharacterIdentificationInput.from_data(
            query=query,
            timeline=state.timeline_data,
            scene=state.scene_data,
            detected_figures=state.judge_result.detected_figures,
        )
        id_result = await self._char_id_agent.run(id_input)

        if not id_result.success or not id_result.content:
            # Fallback to old single-call approach
            logger.warning("Character identification failed, falling back to single-call")
            return await self._step_characters_fallback(state)

        char_identification: CharacterIdentification = id_result.content
        logger.debug(f"Identified {len(char_identification.characters)} characters")

        # === PHASE 2: Graph Generation (from stubs) ===
        # Generate relationship graph BEFORE bios so bios can use relationship context
        logger.debug("Characters Phase 2: Graph generation (relationships inform bios)")
        graph_input = GraphInput(
            query=query,
            year=state.timeline_data.year,
            era=state.timeline_data.era,
            location=state.timeline_data.location,
            characters=[
                {"name": stub.name, "role": stub.role.value}
                for stub in char_identification.characters
            ],
        )
        graph_result = await self._graph_agent.run(graph_input)

        graph_data: GraphData | None = None
        if graph_result.success and graph_result.content:
            graph_data = graph_result.content
            state.graph_data = graph_data  # Store in state for later use
            logger.debug(f"Graph: {len(graph_data.relationships)} relationships generated")
        else:
            logger.warning("Graph generation failed, continuing without relationship context")

        # === PHASE 3: Parallel Bio Generation (with graph context) ===
        logger.debug(f"Characters Phase 3: Parallel bio generation ({len(char_identification.characters)} chars)")

        async def generate_bio_with_semaphore(stub):
            """Generate bio for one character with semaphore control."""
            async with self._semaphore:
                bio_input = CharacterBioInput.from_identification(
                    stub=stub,
                    full_cast=char_identification,
                    query=query,
                    year=state.timeline_data.year,
                    era=state.timeline_data.era,
                    location=state.timeline_data.location,
                    setting=state.scene_data.setting,
                    atmosphere=state.scene_data.atmosphere,
                    tension_level=state.scene_data.tension_level or "medium",
                    graph_data=graph_data,  # Pass graph for relationship context
                )
                return await self._char_bio_agent.run(bio_input)

        # Run all bio generations in parallel
        bio_tasks = [
            generate_bio_with_semaphore(stub)
            for stub in char_identification.characters
        ]
        bio_results = await asyncio.gather(*bio_tasks, return_exceptions=True)

        # Assemble characters from results
        characters: list[Character] = []
        total_latency = id_result.latency_ms + (graph_result.latency_ms if graph_result else 0)
        models_used = [id_result.model_used] if id_result.model_used else []
        if graph_result and graph_result.model_used and graph_result.model_used not in models_used:
            models_used.append(graph_result.model_used)

        for i, result in enumerate(bio_results):
            stub = char_identification.characters[i]
            if isinstance(result, Exception):
                logger.warning(f"Bio generation failed for {stub.name}: {result}")
                characters.append(create_fallback_character(stub))
            elif result.success and result.content:
                characters.append(result.content)
                total_latency += result.latency_ms
                if result.model_used and result.model_used not in models_used:
                    models_used.append(result.model_used)
            else:
                logger.warning(f"Bio generation returned no content for {stub.name}")
                characters.append(create_fallback_character(stub))

        # Build CharacterData from assembled characters
        state.character_data = CharacterData(
            characters=characters,
            focal_character=char_identification.focal_character,
            group_dynamics=char_identification.group_dynamics,
            historical_accuracy_note=char_identification.historical_accuracy_note,
        )

        elapsed_ms = int((time.time() - start_time) * 1000)
        state.step_results.append(
            StepResult(
                step=step,
                success=True,
                data=state.character_data,
                error=None,
                latency_ms=elapsed_ms,
                model_used=", ".join(models_used) if models_used else None,
            )
        )

        logger.debug(f"Characters: {len(characters)} created via graph-informed parallel generation in {elapsed_ms}ms")
        return state

    async def _step_characters_fallback(self, state: PipelineState) -> PipelineState:
        """Single-call character generation (used for FREE tier or parallel failure).

        This method uses the original CharactersAgent which generates all characters
        in a single LLM call. Used when:
        - FREE tier model detected (to avoid rate limits)
        - Parallel character identification fails
        """
        step = PipelineStep.CHARACTERS
        logger.debug("Characters: Using single-call generation")

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
            logger.debug(f"Characters (fallback): {len(state.character_data.characters)} created")
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

        # Pass graph data for relationship-informed dialog
        input_data = DialogInput.from_data(
            query=state.judge_result.cleaned_query or state.query,
            timeline=state.timeline_data,
            scene=state.scene_data,
            characters=state.character_data,
            graph=state.graph_data,  # Relationships inform dialog!
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

        # Pass ALL data for maximum image quality!
        input_data = ImagePromptInput.from_data(
            query=state.judge_result.cleaned_query or state.query,
            timeline=state.timeline_data,
            scene=state.scene_data,
            characters=state.character_data,
            dialog=state.dialog_data,
            graph=state.graph_data,    # Relationships
            moment=state.moment_data,  # Plot/tension
            camera=state.camera_data,  # Composition
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
