"""Tests for generation pipeline.

Tests:
    - Pipeline initialization
    - PipelineState management
    - Step result handling
    - State to Timepoint conversion
"""

import pytest

from app.core.pipeline import (
    GenerationPipeline,
    PipelineState,
    PipelineStep,
    StepResult,
)
from app.schemas import (
    Character,
    CharacterData,
    CharacterRole,
    DialogData,
    DialogLine,
    ImagePromptData,
    JudgeResult,
    QueryType,
    SceneData,
    TimelineData,
)


# PipelineState Tests


@pytest.mark.fast
class TestPipelineState:
    """Tests for PipelineState."""

    def test_create_empty_state(self):
        """Test creating an empty pipeline state."""
        state = PipelineState(query="test query")
        assert state.query == "test query"
        assert state.judge_result is None
        assert state.timeline_data is None
        assert len(state.step_results) == 0

    def test_state_is_valid_false_without_judge(self):
        """Test is_valid is False without judge result."""
        state = PipelineState(query="test")
        assert state.is_valid is False

    def test_state_is_valid_with_valid_judge(self):
        """Test is_valid is True with valid judge result."""
        state = PipelineState(query="test")
        state.judge_result = JudgeResult(is_valid=True, query_type=QueryType.HISTORICAL)
        assert state.is_valid is True

    def test_state_is_valid_with_invalid_judge(self):
        """Test is_valid is False with invalid judge result."""
        state = PipelineState(query="test")
        state.judge_result = JudgeResult(is_valid=False, query_type=QueryType.INVALID)
        assert state.is_valid is False

    def test_state_has_errors_empty(self):
        """Test has_errors with no step results."""
        state = PipelineState(query="test")
        assert state.has_errors is False

    def test_state_has_errors_with_failure(self):
        """Test has_errors with failed step."""
        state = PipelineState(query="test")
        state.step_results.append(
            StepResult(step=PipelineStep.JUDGE, success=False, error="Test error")
        )
        assert state.has_errors is True

    def test_state_current_step(self):
        """Test getting current step."""
        state = PipelineState(query="test")
        assert state.current_step is None

        state.step_results.append(
            StepResult(step=PipelineStep.JUDGE, success=True)
        )
        assert state.current_step == PipelineStep.JUDGE

        state.step_results.append(
            StepResult(step=PipelineStep.TIMELINE, success=True)
        )
        assert state.current_step == PipelineStep.TIMELINE

    def test_get_step_result(self):
        """Test getting specific step result."""
        state = PipelineState(query="test")
        state.step_results.append(
            StepResult(step=PipelineStep.JUDGE, success=True, data="judge_data")
        )
        state.step_results.append(
            StepResult(step=PipelineStep.TIMELINE, success=True, data="timeline_data")
        )

        judge_result = state.get_step_result(PipelineStep.JUDGE)
        assert judge_result is not None
        assert judge_result.data == "judge_data"

        scene_result = state.get_step_result(PipelineStep.SCENE)
        assert scene_result is None


# StepResult Tests


@pytest.mark.fast
class TestStepResult:
    """Tests for StepResult."""

    def test_create_success_result(self):
        """Test creating a successful step result."""
        result = StepResult(
            step=PipelineStep.JUDGE,
            success=True,
            data={"test": "data"},
            latency_ms=100,
            model_used="gemini-3-pro-preview",
        )
        assert result.success is True
        assert result.error is None
        assert result.latency_ms == 100

    def test_create_failure_result(self):
        """Test creating a failed step result."""
        result = StepResult(
            step=PipelineStep.TIMELINE,
            success=False,
            error="API call failed",
            latency_ms=50,
        )
        assert result.success is False
        assert result.error == "API call failed"


# PipelineStep Tests


@pytest.mark.fast
class TestPipelineStep:
    """Tests for PipelineStep enum."""

    def test_pipeline_step_values(self):
        """Test PipelineStep enum values."""
        assert PipelineStep.JUDGE.value == "judge"
        assert PipelineStep.TIMELINE.value == "timeline"
        assert PipelineStep.SCENE.value == "scene"
        assert PipelineStep.CHARACTERS.value == "characters"
        assert PipelineStep.MOMENT.value == "moment"
        assert PipelineStep.DIALOG.value == "dialog"
        assert PipelineStep.CAMERA.value == "camera"
        assert PipelineStep.GRAPH.value == "graph"
        assert PipelineStep.IMAGE_PROMPT.value == "image_prompt"
        assert PipelineStep.IMAGE_GENERATION.value == "image_generation"


# GenerationPipeline Tests


@pytest.mark.fast
class TestGenerationPipeline:
    """Tests for GenerationPipeline."""

    def test_pipeline_initialization(self):
        """Test pipeline initialization."""
        pipeline = GenerationPipeline()
        # Router is lazy-initialized via property, internal state is None
        assert pipeline._router is None
        assert pipeline._agents_initialized is False

    def test_pipeline_initialization_with_router(self):
        """Test pipeline initialization with router."""
        # Create a simple mock router
        from unittest.mock import MagicMock
        mock_router = MagicMock()
        pipeline = GenerationPipeline(router=mock_router)
        assert pipeline.router is mock_router

    def test_state_to_timepoint_completed(self):
        """Test converting completed state to timepoint."""
        state = PipelineState(query="signing of the declaration")
        state.judge_result = JudgeResult(
            is_valid=True,
            query_type=QueryType.HISTORICAL,
            cleaned_query="The signing of the Declaration of Independence",
        )
        state.timeline_data = TimelineData(
            year=1776,
            month=7,
            day=4,
            season="summer",
            location="Independence Hall, Philadelphia",
            era="American Revolution",
        )
        state.scene_data = SceneData(
            setting="The Assembly Room",
            atmosphere="Tense anticipation",
            tension_level="high",
        )
        state.character_data = CharacterData(
            characters=[
                Character(
                    name="John Hancock",
                    role=CharacterRole.PRIMARY,
                    description="President of Congress",
                )
            ]
        )
        state.dialog_data = DialogData(
            lines=[
                DialogLine(speaker="Hancock", text="Gentlemen, the vote is cast.")
            ]
        )
        state.image_prompt_data = ImagePromptData(
            full_prompt="A photorealistic scene...",
            style="historical",
        )

        # All successful
        state.step_results = [
            StepResult(step=PipelineStep.JUDGE, success=True),
            StepResult(step=PipelineStep.TIMELINE, success=True),
            StepResult(step=PipelineStep.SCENE, success=True),
            StepResult(step=PipelineStep.CHARACTERS, success=True),
            StepResult(step=PipelineStep.DIALOG, success=True),
            StepResult(step=PipelineStep.IMAGE_PROMPT, success=True),
        ]

        pipeline = GenerationPipeline()
        timepoint = pipeline.state_to_timepoint(state)

        assert timepoint.query == "signing of the declaration"
        assert timepoint.year == 1776
        assert timepoint.month == 7
        assert timepoint.day == 4
        assert timepoint.location == "Independence Hall, Philadelphia"
        assert timepoint.status.value == "completed"

    def test_state_to_timepoint_failed(self):
        """Test converting failed state to timepoint."""
        state = PipelineState(query="invalid query")
        state.judge_result = JudgeResult(
            is_valid=False,
            query_type=QueryType.INVALID,
            reason="Query too vague",
        )
        state.step_results = [
            StepResult(step=PipelineStep.JUDGE, success=True),
        ]

        pipeline = GenerationPipeline()
        timepoint = pipeline.state_to_timepoint(state)

        assert timepoint.status.value == "failed"

    def test_state_to_generation_logs(self):
        """Test converting state to generation logs."""
        state = PipelineState(query="test query")
        state.step_results = [
            StepResult(
                step=PipelineStep.JUDGE,
                success=True,
                latency_ms=100,
                model_used="gemini-3-pro",
            ),
            StepResult(
                step=PipelineStep.TIMELINE,
                success=False,
                error="API error",
                latency_ms=50,
            ),
        ]

        pipeline = GenerationPipeline()
        logs = pipeline.state_to_generation_logs(state)

        assert len(logs) == 2
        assert logs[0].step == "judge"
        assert logs[0].status == "success"
        assert logs[1].step == "timeline"
        assert logs[1].status == "failed"
        assert logs[1].error_message == "API error"
