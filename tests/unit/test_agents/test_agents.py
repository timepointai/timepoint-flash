"""Tests for all agent implementations.

Tests each agent's:
    - Initialization
    - Prompt generation
    - Input/output types
    - Metadata handling
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.config import ProviderType
from app.agents import (
    JudgeAgent,
    TimelineAgent,
    SceneAgent,
    CharactersAgent,
    MomentAgent,
    DialogAgent,
    CameraAgent,
    GraphAgent,
    ImagePromptAgent,
    ImageGenAgent,
)
from app.agents.timeline import TimelineInput
from app.agents.scene import SceneInput
from app.agents.characters import CharactersInput
from app.agents.moment import MomentInput
from app.agents.dialog import DialogInput
from app.agents.camera import CameraInput
from app.agents.graph import GraphInput
from app.agents.image_prompt import ImagePromptInput
from app.agents.image_gen import ImageGenInput, ImageGenResult
from app.core.providers import LLMResponse
from app.schemas import (
    JudgeResult,
    QueryType,
    TimelineData,
    SceneData,
    CharacterData,
    Character,
    CharacterRole,
    DialogData,
    DialogLine,
    ImagePromptData,
    MomentData,
    CameraData,
    GraphData,
)


# Judge Agent Tests


@pytest.mark.fast
class TestJudgeAgent:
    """Tests for JudgeAgent."""

    def test_initialization(self):
        """Test JudgeAgent initialization."""
        agent = JudgeAgent()
        assert agent.name == "JudgeAgent"
        assert agent.response_model == JudgeResult

    def test_get_system_prompt(self):
        """Test system prompt."""
        agent = JudgeAgent()
        prompt = agent.get_system_prompt()
        assert "temporal query validator" in prompt.lower()

    def test_get_prompt(self):
        """Test user prompt generation."""
        agent = JudgeAgent()
        prompt = agent.get_prompt("signing of the declaration")
        assert "signing of the declaration" in prompt

    @pytest.mark.asyncio
    async def test_run_valid_query(self):
        """Test running with valid query."""
        mock_router = MagicMock()
        mock_router.call_structured = AsyncMock(
            return_value=LLMResponse(
                content=JudgeResult(
                    is_valid=True,
                    query_type=QueryType.HISTORICAL,
                    cleaned_query="The signing of the Declaration of Independence",
                ),
                model="test-model",
                provider=ProviderType.GOOGLE,
            )
        )

        agent = JudgeAgent(router=mock_router)
        result = await agent.run("signing of the declaration")

        assert result.success is True
        assert result.content.is_valid is True
        assert result.metadata["is_valid"] is True

    def test_create_failed_result(self):
        """Test creating failed result."""
        result = JudgeAgent.create_failed_result("API timeout")
        assert result.is_valid is False
        assert result.query_type == QueryType.INVALID
        assert result.reason == "API timeout"


# Timeline Agent Tests


@pytest.mark.fast
class TestTimelineAgent:
    """Tests for TimelineAgent."""

    def test_initialization(self):
        """Test TimelineAgent initialization."""
        agent = TimelineAgent()
        assert agent.name == "TimelineAgent"
        assert agent.response_model == TimelineData

    def test_get_prompt(self):
        """Test user prompt generation."""
        agent = TimelineAgent()
        input_data = TimelineInput(
            query="rome 50 BCE",
            query_type="historical",
            detected_year=-50,
        )
        prompt = agent.get_prompt(input_data)
        assert "rome 50 BCE" in prompt
        assert "historical" in prompt

    def test_timeline_input_from_judge(self):
        """Test creating TimelineInput from JudgeResult."""
        judge = JudgeResult(
            is_valid=True,
            query_type=QueryType.HISTORICAL,
            cleaned_query="Ancient Rome, 50 BCE",
            detected_year=-50,
            detected_location="Rome",
        )
        input_data = TimelineInput.from_judge_result("rome 50 BCE", judge)
        assert input_data.query == "Ancient Rome, 50 BCE"
        assert input_data.detected_year == -50
        assert input_data.detected_location == "Rome"


# Scene Agent Tests


@pytest.mark.fast
class TestSceneAgent:
    """Tests for SceneAgent."""

    def test_initialization(self):
        """Test SceneAgent initialization."""
        agent = SceneAgent()
        assert agent.name == "SceneAgent"
        assert agent.response_model == SceneData

    def test_scene_input_from_timeline(self):
        """Test creating SceneInput from TimelineData."""
        timeline = TimelineData(
            year=1776,
            month=7,
            day=4,
            season="summer",
            location="Independence Hall",
            era="American Revolution",
            historical_context="Declaration signing",
        )
        input_data = SceneInput.from_timeline("signing", timeline)
        assert input_data.year == 1776
        assert input_data.season == "summer"
        assert input_data.location == "Independence Hall"


# Characters Agent Tests


@pytest.mark.fast
class TestCharactersAgent:
    """Tests for CharactersAgent."""

    def test_initialization(self):
        """Test CharactersAgent initialization."""
        agent = CharactersAgent()
        assert agent.name == "CharactersAgent"
        assert agent.response_model == CharacterData

    @pytest.mark.asyncio
    async def test_run_with_mock(self):
        """Test running with mock router."""
        mock_router = MagicMock()
        mock_router.call_structured = AsyncMock(
            return_value=LLMResponse(
                content=CharacterData(
                    characters=[
                        Character(
                            name="John Hancock",
                            role=CharacterRole.PRIMARY,
                            description="President of Congress",
                        ),
                    ],
                    focal_character="John Hancock",
                ),
                model="test-model",
                provider=ProviderType.GOOGLE,
            )
        )

        agent = CharactersAgent(router=mock_router)
        input_data = CharactersInput(
            query="signing",
            year=1776,
            detected_figures=["John Hancock"],
        )
        result = await agent.run(input_data)

        assert result.success is True
        assert len(result.content.characters) == 1
        assert result.metadata["character_count"] == 1


# Moment Agent Tests


@pytest.mark.fast
class TestMomentAgent:
    """Tests for MomentAgent."""

    def test_initialization(self):
        """Test MomentAgent initialization."""
        agent = MomentAgent()
        assert agent.name == "MomentAgent"
        assert agent.response_model == MomentData

    def test_get_prompt(self):
        """Test user prompt generation."""
        agent = MomentAgent()
        input_data = MomentInput(
            query="signing of the declaration",
            year=1776,
            era="American Revolution",
            location="Independence Hall",
            setting="Assembly Room",
            atmosphere="Tense anticipation",
            characters=["John Hancock"],
        )
        prompt = agent.get_prompt(input_data)
        assert "signing of the declaration" in prompt
        assert "John Hancock" in prompt


# Dialog Agent Tests


@pytest.mark.fast
class TestDialogAgent:
    """Tests for DialogAgent."""

    def test_initialization(self):
        """Test DialogAgent initialization."""
        agent = DialogAgent()
        assert agent.name == "DialogAgent"
        assert agent.response_model == DialogData

    @pytest.mark.asyncio
    async def test_run_with_mock(self):
        """Test running with mock router."""
        mock_router = MagicMock()
        mock_router.call_structured = AsyncMock(
            return_value=LLMResponse(
                content=DialogData(
                    lines=[
                        DialogLine(speaker="Hancock", text="The time has come."),
                        DialogLine(speaker="Franklin", text="Indeed it has."),
                    ],
                    language_style="18th century formal",
                ),
                model="test-model",
                provider=ProviderType.GOOGLE,
            )
        )

        agent = DialogAgent(router=mock_router)
        input_data = DialogInput(
            query="signing",
            year=1776,
            speaking_characters=["Hancock", "Franklin"],
        )
        result = await agent.run(input_data)

        assert result.success is True
        assert result.metadata["line_count"] == 2
        assert "Hancock" in result.metadata["speakers"]


@pytest.mark.fast
class TestDialogInputWithMoment:
    """Tests for DialogInput with MomentData and DialogArc."""

    def test_dialog_input_from_data_with_moment(self):
        """Test DialogInput.from_data includes moment_data."""
        from app.schemas.moment import MomentData

        timeline = TimelineData(
            year=1776, location="Philadelphia", era="Revolution",
        )
        scene = SceneData(
            setting="Assembly Room", atmosphere="Tense", tension_level="high",
        )
        characters = CharacterData(
            characters=[
                Character(name="Hancock", role=CharacterRole.PRIMARY, description="President", speaks_in_scene=True),
                Character(name="Franklin", role=CharacterRole.SECONDARY, description="Diplomat", speaks_in_scene=True),
            ],
            focal_character="Hancock",
        )
        moment = MomentData(
            plot_summary="The signing",
            tension_arc="climactic",
            stakes="Independence",
            central_question="Will they sign?",
        )

        input_data = DialogInput.from_data(
            query="signing of the declaration",
            timeline=timeline,
            scene=scene,
            characters=characters,
            moment=moment,
        )

        assert input_data.moment_data is not None
        assert input_data.moment_data.tension_arc == "climactic"
        assert input_data.dialog_arc is not None
        assert len(input_data.dialog_arc.beats) == 7

    def test_dialog_input_from_data_without_moment(self):
        """Test DialogInput.from_data works without moment."""
        timeline = TimelineData(year=1776, location="Philadelphia", era="Revolution")
        scene = SceneData(setting="Room", atmosphere="Tense", tension_level="high")
        characters = CharacterData(
            characters=[
                Character(name="Hancock", role=CharacterRole.PRIMARY, description="President", speaks_in_scene=True),
            ],
            focal_character="Hancock",
        )

        input_data = DialogInput.from_data(
            query="signing",
            timeline=timeline,
            scene=scene,
            characters=characters,
        )

        assert input_data.moment_data is None
        assert input_data.dialog_arc is None

    def test_dialog_input_speaker_limit_6(self):
        """Test DialogInput limits speakers to 6."""
        timeline = TimelineData(year=1776, location="Philadelphia", era="Revolution")
        scene = SceneData(setting="Room", atmosphere="Tense", tension_level="high")
        chars = [
            Character(name=f"Char{i}", role=CharacterRole.SECONDARY, description=f"Person {i}", speaks_in_scene=True)
            for i in range(8)
        ]
        characters = CharacterData(characters=chars, focal_character="Char0")

        input_data = DialogInput.from_data(
            query="test",
            timeline=timeline,
            scene=scene,
            characters=characters,
        )

        assert len(input_data.speaking_characters) <= 6

    def test_dialog_input_relationship_context(self):
        """Test get_relationship_context returns relationship info."""
        from app.schemas.graph import Relationship

        input_data = DialogInput(
            query="test",
            year=1776,
            relationships=[
                Relationship(
                    from_character="Adams",
                    to_character="Jefferson",
                    relationship_type="ally",
                    description="Fellow founding fathers",
                )
            ],
        )

        ctx = input_data.get_relationship_context("Adams", "Jefferson")
        assert "ally" in ctx
        assert "Adams" in ctx


# Camera Agent Tests


@pytest.mark.fast
class TestCameraAgent:
    """Tests for CameraAgent."""

    def test_initialization(self):
        """Test CameraAgent initialization."""
        agent = CameraAgent()
        assert agent.name == "CameraAgent"
        assert agent.response_model == CameraData

    def test_get_prompt(self):
        """Test user prompt generation."""
        agent = CameraAgent()
        input_data = CameraInput(
            query="signing",
            setting="Assembly Room",
            atmosphere="Tense",
            tension_level="high",
            focal_point="Signing table",
        )
        prompt = agent.get_prompt(input_data)
        assert "Assembly Room" in prompt
        assert "Signing table" in prompt


# Graph Agent Tests


@pytest.mark.fast
class TestGraphAgent:
    """Tests for GraphAgent."""

    def test_initialization(self):
        """Test GraphAgent initialization."""
        agent = GraphAgent()
        assert agent.name == "GraphAgent"
        assert agent.response_model == GraphData

    def test_get_prompt(self):
        """Test user prompt generation."""
        agent = GraphAgent()
        input_data = GraphInput(
            query="signing",
            year=1776,
            era="American Revolution",
            location="Philadelphia",
            characters=[
                {"name": "John Adams", "role": "primary"},
                {"name": "Thomas Jefferson", "role": "primary"},
            ],
        )
        prompt = agent.get_prompt(input_data)
        assert "John Adams" in prompt
        assert "Thomas Jefferson" in prompt


# Image Prompt Agent Tests


@pytest.mark.fast
class TestImagePromptAgent:
    """Tests for ImagePromptAgent."""

    def test_initialization(self):
        """Test ImagePromptAgent initialization."""
        agent = ImagePromptAgent()
        assert agent.name == "ImagePromptAgent"
        assert agent.response_model == ImagePromptData

    @pytest.mark.asyncio
    async def test_run_with_mock(self):
        """Test running with mock router."""
        mock_router = MagicMock()
        mock_router.call_structured = AsyncMock(
            return_value=LLMResponse(
                content=ImagePromptData(
                    full_prompt="A photorealistic scene of...",
                    style="photorealistic",
                    composition_notes="Wide shot",
                ),
                model="test-model",
                provider=ProviderType.GOOGLE,
            )
        )

        agent = ImagePromptAgent(router=mock_router)
        input_data = ImagePromptInput(
            query="signing",
            year=1776,
            location="Philadelphia",
            setting="Assembly Room",
            atmosphere="Historic",
            character_descriptions=["John Hancock at the table"],
        )
        result = await agent.run(input_data)

        assert result.success is True
        assert result.metadata["style"] == "photorealistic"


# Image Gen Agent Tests


@pytest.mark.fast
class TestImageGenAgent:
    """Tests for ImageGenAgent."""

    def test_initialization(self):
        """Test ImageGenAgent initialization."""
        agent = ImageGenAgent()
        assert agent.name == "ImageGenAgent"

    def test_get_prompt(self):
        """Test prompt formatting."""
        agent = ImageGenAgent()
        input_data = ImageGenInput(
            prompt="A beautiful scene",
            style="photorealistic",
        )
        prompt = agent.get_prompt(input_data)
        assert "photorealistic" in prompt
        assert "beautiful scene" in prompt

    @pytest.mark.asyncio
    async def test_run_with_mock(self):
        """Test running with mock router."""
        mock_router = MagicMock()
        mock_router.generate_image = AsyncMock(
            return_value=LLMResponse(
                content="base64imagedata...",
                model="imagen-3",
                provider=ProviderType.GOOGLE,
            )
        )

        agent = ImageGenAgent(router=mock_router)
        input_data = ImageGenInput(prompt="A scene")
        result = await agent.run(input_data)

        assert result.success is True
        assert result.content.image_base64 == "base64imagedata..."
        assert result.content.model_used == "imagen-3"

    @pytest.mark.asyncio
    async def test_run_failure(self):
        """Test handling generation failure."""
        mock_router = MagicMock()
        mock_router.generate_image = AsyncMock(
            side_effect=Exception("Generation failed")
        )

        agent = ImageGenAgent(router=mock_router)
        input_data = ImageGenInput(prompt="A scene")
        result = await agent.run(input_data)

        assert result.success is False
        assert "Generation failed" in result.error
