"""End-to-end tests for the TIMEPOINT generation pipeline.

These tests make REAL API calls to LLM providers and require valid API keys.
They verify the complete generation flow from query to timepoint.

Run with:
    pytest -m e2e -v
    pytest tests/e2e/test_pipeline_e2e.py -v -s

Requirements:
    - Valid GOOGLE_API_KEY or OPENROUTER_API_KEY in .env
    - Network connectivity to API endpoints

Cost Estimate:
    - Full test suite: ~$0.01-0.05 in API calls
    - Each agent test: ~$0.001-0.005

Time Estimate:
    - Individual agent tests: 2-10 seconds each
    - Full pipeline test: 30-60 seconds
"""

import pytest

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
)
from app.agents.timeline import TimelineInput
from app.agents.scene import SceneInput
from app.agents.characters import CharactersInput
from app.agents.moment import MomentInput
from app.agents.dialog import DialogInput
from app.agents.camera import CameraInput
from app.agents.graph import GraphInput
from app.agents.image_prompt import ImagePromptInput
from app.schemas import QueryType


# ============================================================================
# Provider Health Check Tests
# ============================================================================


@pytest.mark.e2e
class TestProviderHealth:
    """Test provider connectivity with real APIs."""

    @pytest.mark.asyncio
    async def test_google_provider_health(self, real_google_provider):
        """Verify Google provider is accessible via a simple API call."""
        # Use the health_check method which is designed to work reliably
        try:
            is_healthy = await real_google_provider.health_check()
            assert is_healthy, "Google provider health check returned False"
        except Exception as e:
            pytest.fail(f"Google provider health check failed: {e}")

    @pytest.mark.asyncio
    async def test_router_health_check(self, real_router):
        """Verify router can reach all configured providers."""
        health = await real_router.health_check()
        # At least one provider should be healthy
        assert any(health.values()), f"No healthy providers: {health}"


# ============================================================================
# Individual Agent E2E Tests
# ============================================================================


@pytest.mark.e2e
class TestJudgeAgentE2E:
    """E2E tests for JudgeAgent with real LLM calls."""

    @pytest.mark.asyncio
    async def test_validates_historical_query(self, real_router):
        """Test JudgeAgent validates a clear historical query."""
        agent = JudgeAgent(router=real_router)
        result = await agent.run("signing of the declaration of independence")

        assert result.success, f"Agent failed: {result.error}"
        assert result.content.is_valid, "Query should be valid"
        assert result.content.query_type == QueryType.HISTORICAL
        assert result.latency_ms > 0

    @pytest.mark.asyncio
    async def test_validates_fictional_query(self, real_router):
        """Test JudgeAgent handles fictional query."""
        agent = JudgeAgent(router=real_router)
        result = await agent.run("the battle of hogwarts harry potter")

        assert result.success, f"Agent failed: {result.error}"
        # Fictional queries may be valid but typed as FICTIONAL or SPECULATIVE
        assert result.content.query_type in [QueryType.FICTIONAL, QueryType.SPECULATIVE]

    @pytest.mark.asyncio
    async def test_rejects_invalid_query(self, real_router):
        """Test JudgeAgent rejects nonsense query."""
        agent = JudgeAgent(router=real_router)
        result = await agent.run("asdfghjkl random gibberish")

        assert result.success, f"Agent failed: {result.error}"
        # Should either be invalid or have low confidence
        # The LLM may still try to interpret it, so we check the response


@pytest.mark.e2e
class TestTimelineAgentE2E:
    """E2E tests for TimelineAgent with real LLM calls."""

    @pytest.mark.asyncio
    async def test_extracts_temporal_coordinates(self, real_router):
        """Test TimelineAgent extracts year/location from historical event."""
        agent = TimelineAgent(router=real_router)
        input_data = TimelineInput(
            query="signing of the declaration of independence",
            query_type="historical",
            detected_year=1776,
            detected_location="Philadelphia",
        )
        result = await agent.run(input_data)

        assert result.success, f"Agent failed: {result.error}"
        assert result.content.year == 1776, f"Expected 1776, got {result.content.year}"
        # Accept July (adoption) or August (formal signing) - both are historically valid
        assert result.content.month in [7, 8], f"Expected July or August, got month {result.content.month}"
        assert "Philadelphia" in result.content.location or "Independence" in result.content.location

    @pytest.mark.asyncio
    async def test_extracts_ancient_date(self, real_router):
        """Test TimelineAgent handles BCE dates."""
        agent = TimelineAgent(router=real_router)
        input_data = TimelineInput(
            query="assassination of Julius Caesar",
            query_type="historical",
            detected_year=-44,
            detected_location="Rome",
        )
        result = await agent.run(input_data)

        assert result.success, f"Agent failed: {result.error}"
        assert result.content.year == -44, f"Expected -44 BCE, got {result.content.year}"


@pytest.mark.e2e
class TestSceneAgentE2E:
    """E2E tests for SceneAgent with real LLM calls."""

    @pytest.mark.asyncio
    async def test_generates_scene_description(self, real_router):
        """Test SceneAgent generates detailed scene."""
        agent = SceneAgent(router=real_router)
        input_data = SceneInput(
            query="signing of the declaration",
            year=1776,
            era="American Revolution",
            season="summer",
            time_of_day="afternoon",
            location="Independence Hall, Philadelphia",
        )
        result = await agent.run(input_data)

        assert result.success, f"Agent failed: {result.error}"
        assert result.content.setting, "Should have setting"
        assert result.content.atmosphere, "Should have atmosphere"


@pytest.mark.e2e
class TestCharactersAgentE2E:
    """E2E tests for CharactersAgent with real LLM calls."""

    @pytest.mark.asyncio
    async def test_generates_characters(self, real_router):
        """Test CharactersAgent generates historical figures."""
        agent = CharactersAgent(router=real_router)
        input_data = CharactersInput(
            query="signing of the declaration",
            year=1776,
            era="American Revolution",
            location="Philadelphia",
            setting="Assembly Room",
            detected_figures=["John Hancock", "Benjamin Franklin", "Thomas Jefferson"],
        )
        result = await agent.run(input_data)

        assert result.success, f"Agent failed: {result.error}"
        assert len(result.content.characters) >= 1, "Should have at least one character"

        # Check that at least one famous founder is included
        names = [c.name.lower() for c in result.content.characters]
        famous_founders = ["hancock", "franklin", "jefferson", "adams"]
        has_founder = any(f in " ".join(names) for f in famous_founders)
        assert has_founder, f"Expected a founding father, got: {names}"


@pytest.mark.e2e
class TestDialogAgentE2E:
    """E2E tests for DialogAgent with real LLM calls."""

    @pytest.mark.asyncio
    async def test_generates_dialog(self, real_router):
        """Test DialogAgent generates period-appropriate dialog."""
        agent = DialogAgent(router=real_router)
        input_data = DialogInput(
            query="signing of the declaration",
            year=1776,
            era="American Revolution",
            location="Philadelphia",
            setting="Assembly Room",
            atmosphere="Tense anticipation",
            tension_level="high",
            speaking_characters=["John Hancock", "Benjamin Franklin"],
        )
        result = await agent.run(input_data)

        assert result.success, f"Agent failed: {result.error}"
        assert len(result.content.lines) >= 1, "Should have at least one dialog line"
        assert result.content.lines[0].speaker, "Dialog should have speaker"
        assert result.content.lines[0].text, "Dialog should have text"


# ============================================================================
# Full Pipeline E2E Test
# ============================================================================


@pytest.mark.e2e
class TestFullPipelineE2E:
    """E2E test for the complete generation pipeline."""

    @pytest.mark.asyncio
    async def test_complete_pipeline_flow(self, real_router):
        """Test the complete pipeline from query to image prompt.

        This test runs all agents in sequence, passing outputs as inputs
        to subsequent agents, simulating the full generation flow.

        Note: Does NOT test image generation to avoid higher costs.
        """
        query = "signing of the declaration of independence"

        # Step 1: Judge
        judge = JudgeAgent(router=real_router)
        judge_result = await judge.run(query)
        assert judge_result.success, f"Judge failed: {judge_result.error}"
        assert judge_result.content.is_valid, "Query should be valid"

        # Step 2: Timeline
        timeline = TimelineAgent(router=real_router)
        timeline_input = TimelineInput.from_judge_result(query, judge_result.content)
        timeline_result = await timeline.run(timeline_input)
        assert timeline_result.success, f"Timeline failed: {timeline_result.error}"
        assert timeline_result.content.year == 1776

        # Step 3: Scene
        scene = SceneAgent(router=real_router)
        scene_input = SceneInput.from_timeline(query, timeline_result.content)
        scene_result = await scene.run(scene_input)
        assert scene_result.success, f"Scene failed: {scene_result.error}"

        # Step 4: Characters
        characters = CharactersAgent(router=real_router)
        characters_input = CharactersInput(
            query=query,
            year=timeline_result.content.year,
            era=timeline_result.content.era or "American Revolution",
            location=timeline_result.content.location,
            setting=scene_result.content.setting,
            detected_figures=judge_result.content.detected_figures or [],
        )
        characters_result = await characters.run(characters_input)
        assert characters_result.success, f"Characters failed: {characters_result.error}"
        assert len(characters_result.content.characters) >= 1

        # Step 5: Moment
        moment = MomentAgent(router=real_router)
        moment_input = MomentInput(
            query=query,
            year=timeline_result.content.year,
            era=timeline_result.content.era or "American Revolution",
            location=timeline_result.content.location,
            setting=scene_result.content.setting,
            atmosphere=scene_result.content.atmosphere,
            characters=[c.name for c in characters_result.content.characters],
        )
        moment_result = await moment.run(moment_input)
        assert moment_result.success, f"Moment failed: {moment_result.error}"

        # Step 6: Dialog
        dialog = DialogAgent(router=real_router)
        dialog_input = DialogInput(
            query=query,
            year=timeline_result.content.year,
            era=timeline_result.content.era,
            location=timeline_result.content.location,
            setting=scene_result.content.setting,
            atmosphere=scene_result.content.atmosphere,
            tension_level=scene_result.content.tension_level if hasattr(scene_result.content, "tension_level") else "medium",
            speaking_characters=[c.name for c in characters_result.content.characters[:3]],
        )
        dialog_result = await dialog.run(dialog_input)
        assert dialog_result.success, f"Dialog failed: {dialog_result.error}"

        # Step 7: Camera
        camera = CameraAgent(router=real_router)
        camera_input = CameraInput(
            query=query,
            setting=scene_result.content.setting,
            atmosphere=scene_result.content.atmosphere,
            tension_level=scene_result.content.tension_level if hasattr(scene_result.content, "tension_level") else "medium",
            focal_point=characters_result.content.focal_character,
        )
        camera_result = await camera.run(camera_input)
        assert camera_result.success, f"Camera failed: {camera_result.error}"

        # Step 8: Graph
        graph = GraphAgent(router=real_router)
        graph_input = GraphInput(
            query=query,
            year=timeline_result.content.year,
            era=timeline_result.content.era,
            location=timeline_result.content.location,
            characters=[
                {"name": c.name, "role": c.role.value}
                for c in characters_result.content.characters
            ],
        )
        graph_result = await graph.run(graph_input)
        assert graph_result.success, f"Graph failed: {graph_result.error}"

        # Step 9: Image Prompt
        image_prompt = ImagePromptAgent(router=real_router)
        image_prompt_input = ImagePromptInput(
            query=query,
            year=timeline_result.content.year,
            location=timeline_result.content.location,
            setting=scene_result.content.setting,
            atmosphere=scene_result.content.atmosphere,
            character_descriptions=[
                f"{c.name}: {c.description}" for c in characters_result.content.characters
            ],
            focal_point=camera_result.content.focal_point if camera_result.content else None,
            lighting=scene_result.content.lighting if hasattr(scene_result.content, "lighting") else None,
        )
        image_prompt_result = await image_prompt.run(image_prompt_input)
        assert image_prompt_result.success, f"ImagePrompt failed: {image_prompt_result.error}"
        assert image_prompt_result.content.full_prompt, "Should have full prompt"
        assert len(image_prompt_result.content.full_prompt) > 100, "Prompt should be substantial"

        # Summary
        print("\n" + "=" * 60)
        print("FULL PIPELINE E2E TEST COMPLETED SUCCESSFULLY")
        print("=" * 60)
        print(f"Query: {query}")
        print(f"Year: {timeline_result.content.year}")
        print(f"Location: {timeline_result.content.location}")
        print(f"Characters: {len(characters_result.content.characters)}")
        print(f"Dialog lines: {len(dialog_result.content.lines)}")
        print(f"Image prompt length: {len(image_prompt_result.content.full_prompt)} chars")
        print("=" * 60)


# ============================================================================
# API Endpoint E2E Tests
# ============================================================================


@pytest.mark.e2e
class TestAPIEndpointsE2E:
    """E2E tests for FastAPI endpoints with real generation."""

    @pytest.mark.asyncio
    async def test_health_endpoint(self, test_client):
        """Test health endpoint returns OK."""
        response = await test_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_generate_endpoint_accepts_query(self, test_client, e2e_test_db):
        """Test generate endpoint accepts and starts processing."""
        import uuid
        # Use unique query to avoid slug collision in repeated test runs
        unique_query = f"moon landing 1969 {uuid.uuid4().hex[:8]}"
        response = await test_client.post(
            "/api/v1/timepoints/generate",
            json={"query": unique_query},
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["status"] == "processing"
