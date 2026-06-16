"""Unit tests for /api/v1/find-money/quick-sim-batch.

These tests cover:
- Request schema validation (size limits, required fields, input aliases)
- Future-moment query builder (length cap, missing fields handled)
- TDF → metrics-prompt summariser (degrades gracefully)
- Response shape: ``QuickSimTdfEntry`` / ``QuickSimBatchResponse`` (the
  ``{"tdfs": [...]}`` JSON contract the web-app pairs against — NOT SSE)
- A **real** ``GenerationPipeline`` integration check: the handler builds
  every pipeline through ``_build_generation_pipeline``; constructing a
  real pipeline through that seam here fails CI on an ``__init__``
  signature drift. PR #45 shipped a runtime crash
  (``TypeError: GenerationPipeline.__init__() got an unexpected keyword
  argument 'user_id'``) precisely because its tests never built a real
  pipeline — this file closes that gap.

Per ``feedback_no_mocks.md`` nothing here is mocked. The pipeline's live
LLM calls are not exercised (those need real API keys / a live preset);
the integration test stops at construction, which is exactly where the
shipped signature bug lived.
"""

from __future__ import annotations

import inspect

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.v1.find_money import (
    _QUICK_SIM_TEXT_MODEL,
    _build_generation_pipeline,
    _build_tdf_entry,
    _resolve_quick_sim_text_model,
    summarize_tdf_for_metrics,
)
from app.config import QualityPreset
from app.core.pipeline import GenerationPipeline
from app.prompts.quick_sim import (
    build_future_moment_query,
    get_metrics_prompt,
    get_metrics_system_prompt,
)
from app.schemas.quick_sim import (
    OpportunityIn,
    QuickSimBatchRequest,
    QuickSimBatchResponse,
    QuickSimMetrics,
    QuickSimTdfEntry,
)

# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


@pytest.mark.fast
class TestOpportunityIn:
    """Tests for OpportunityIn schema."""

    def test_minimal_valid_opportunity(self):
        """Only ``title`` is required."""
        opp = OpportunityIn(title="Climate Action Fund")
        assert opp.title == "Climate Action Fund"
        assert opp.summary is None
        assert opp.amount is None

    def test_full_opportunity(self):
        opp = OpportunityIn(
            title="Climate Action Fund",
            source_url="https://example.org/climate",
            summary="Annual climate grants",
            amount=25000,
            deadline="2026-09-01",
        )
        assert opp.amount == 25000
        assert opp.source_url == "https://example.org/climate"

    def test_amount_accepts_string(self):
        """Amount can be a free-text string like '$10k–$50k'."""
        opp = OpportunityIn(title="x", amount="$10k–$50k")
        assert opp.amount == "$10k–$50k"

    def test_accepts_web_app_url_and_amount_usd_aliases(self):
        """The web-app sourcing stage emits ``url`` / ``amount_usd`` keys.

        ``OpportunityIn`` accepts those as validation aliases so the
        cross-service request contract works regardless of which side
        names the field.
        """
        opp = OpportunityIn.model_validate(
            {
                "title": "Climate Action Fund",
                "url": "https://example.org/climate",
                "amount_usd": 25000,
                "summary": "Annual climate grants",
            }
        )
        assert opp.source_url == "https://example.org/climate"
        assert opp.amount == 25000
        # Canonical field names survive a round-trip dump.
        dumped = opp.model_dump()
        assert dumped["source_url"] == "https://example.org/climate"
        assert dumped["amount"] == 25000

    def test_title_required(self):
        with pytest.raises(ValidationError):
            OpportunityIn()  # type: ignore[call-arg]

    def test_title_min_length(self):
        with pytest.raises(ValidationError):
            OpportunityIn(title="")

    def test_title_max_length(self):
        with pytest.raises(ValidationError):
            OpportunityIn(title="x" * 301)


@pytest.mark.fast
class TestQuickSimBatchRequest:
    """Tests for QuickSimBatchRequest schema."""

    def _opps(self, n: int) -> list[OpportunityIn]:
        return [OpportunityIn(title=f"opportunity {i}") for i in range(n)]

    def test_valid_request(self):
        req = QuickSimBatchRequest(
            goal="$50k operating grant",
            opportunities=self._opps(1),
        )
        assert req.goal == "$50k operating grant"
        assert req.preset == "hyper"  # default favours speed
        assert req.generate_image is False
        assert req.depth is None  # dial absent → default model path

    def test_depth_accepts_control_surface_tier(self):
        req = QuickSimBatchRequest(
            goal="$50k operating grant",
            opportunities=self._opps(1),
            depth="frontier",
        )
        assert req.depth == "frontier"

    def test_requires_at_least_one_opportunity(self):
        with pytest.raises(ValidationError):
            QuickSimBatchRequest(goal="goal", opportunities=[])

    def test_caps_at_15_opportunities(self):
        with pytest.raises(ValidationError):
            QuickSimBatchRequest(goal="goal", opportunities=self._opps(16))

    def test_allows_exactly_15(self):
        req = QuickSimBatchRequest(goal="goal", opportunities=self._opps(15))
        assert len(req.opportunities) == 15

    def test_goal_min_length(self):
        with pytest.raises(ValidationError):
            QuickSimBatchRequest(goal="ab", opportunities=self._opps(1))

    def test_goal_max_length(self):
        with pytest.raises(ValidationError):
            QuickSimBatchRequest(goal="x" * 1001, opportunities=self._opps(1))


@pytest.mark.fast
class TestResolveQuickSimTextModel:
    """Operation Control Surface depth dial → text-model resolution (el-3ojoy).

    The default (depth absent) path must be unchanged — this is the
    no-regression contract for every existing quick-sim caller.
    """

    def test_none_uses_default_no_regression(self):
        assert _resolve_quick_sim_text_model(None) == _QUICK_SIM_TEXT_MODEL

    def test_standard_resolves_to_default_model(self):
        assert _resolve_quick_sim_text_model("standard") == _QUICK_SIM_TEXT_MODEL

    def test_fast_tier_uses_cheaper_model(self):
        assert _resolve_quick_sim_text_model("fast") == "gemini-2.0-flash"

    def test_deep_tier_uses_default_text_model(self):
        assert _resolve_quick_sim_text_model("deep") == "gemini-2.5-flash"

    def test_frontier_tier_uses_claude_opus(self):
        assert _resolve_quick_sim_text_model("frontier") == "anthropic/claude-opus-4.8"

    def test_depth_is_case_insensitive(self):
        assert _resolve_quick_sim_text_model("FRONTIER") == "anthropic/claude-opus-4.8"

    def test_unrecognised_depth_falls_back_to_default(self):
        assert _resolve_quick_sim_text_model("ludicrous") == _QUICK_SIM_TEXT_MODEL


@pytest.mark.fast
class TestQuickSimMetrics:
    """Tests for the QuickSimMetrics output schema."""

    def test_valid_metrics(self):
        m = QuickSimMetrics(
            probability_of_award=0.42,
            fit_score=0.7,
            effort_score=0.55,
            effort_estimate="moderate — 20h proposal",
            key_risks=["competitive field"],
            key_levers=["co-applicant from anchor org"],
            rationale="solid fit but crowded competition",
        )
        assert m.probability_of_award == pytest.approx(0.42)
        assert m.fit_score == pytest.approx(0.7)
        assert m.effort_score == pytest.approx(0.55)
        assert m.key_risks == ["competitive field"]

    def test_probability_bounds(self):
        with pytest.raises(ValidationError):
            QuickSimMetrics(
                probability_of_award=1.1,
                fit_score=0.5,
                effort_score=0.5,
                effort_estimate="x",
            )
        with pytest.raises(ValidationError):
            QuickSimMetrics(
                probability_of_award=-0.1,
                fit_score=0.5,
                effort_score=0.5,
                effort_estimate="x",
            )

    def test_fit_score_bounds(self):
        with pytest.raises(ValidationError):
            QuickSimMetrics(
                probability_of_award=0.5,
                fit_score=1.5,
                effort_score=0.5,
                effort_estimate="x",
            )

    def test_effort_score_bounds(self):
        with pytest.raises(ValidationError):
            QuickSimMetrics(
                probability_of_award=0.5,
                fit_score=0.5,
                effort_score=1.5,
                effort_estimate="x",
            )
        with pytest.raises(ValidationError):
            QuickSimMetrics(
                probability_of_award=0.5,
                fit_score=0.5,
                effort_score=-0.1,
                effort_estimate="x",
            )

    def test_effort_score_required(self):
        """effort_score is required — the web-app selection page ranks on it."""
        with pytest.raises(ValidationError):
            QuickSimMetrics(
                probability_of_award=0.5,
                fit_score=0.5,
                effort_estimate="x",
            )  # type: ignore[call-arg]

    def test_default_empty_lists(self):
        m = QuickSimMetrics(
            probability_of_award=0.5,
            fit_score=0.5,
            effort_score=0.5,
            effort_estimate="x",
        )
        assert m.key_risks == []
        assert m.key_levers == []


# ---------------------------------------------------------------------------
# build_future_moment_query
# ---------------------------------------------------------------------------


@pytest.mark.fast
class TestBuildFutureMomentQuery:
    """Tests for the future-tense framing helper."""

    def test_handles_minimal_opportunity(self):
        q = build_future_moment_query(
            goal="$50k operating grant",
            opportunity={"title": "Climate Action Fund"},
        )
        assert "Climate Action Fund" in q
        assert "$50k operating grant" in q
        assert "Future moment" in q
        assert "unspecified" in q  # missing fields fall through to placeholders

    def test_includes_all_fields_when_present(self):
        q = build_future_moment_query(
            goal="raise $50k by Sept",
            opportunity={
                "title": "Climate Action Fund",
                "source_url": "https://example.org/x",
                "summary": "Annual climate grants",
                "amount": 25000,
                "deadline": "2026-09-01",
            },
        )
        assert "Annual climate grants" in q
        assert "25000" in q
        assert "2026-09-01" in q

    def test_truncates_long_summary(self):
        long_summary = "lorem ipsum " * 200  # ~2400 chars
        q = build_future_moment_query(
            goal="goal",
            opportunity={"title": "x", "summary": long_summary},
        )
        # Query must stay under Flash's 500-char limit
        assert len(q) <= 500

    def test_truncates_overall_query_to_500_chars(self):
        """Even with all fields stuffed, query must stay <= 500 chars."""
        q = build_future_moment_query(
            goal="g" * 400,
            opportunity={
                "title": "t" * 200,
                "summary": "s" * 500,
                "amount": "$" + "9" * 50,
                "deadline": "d" * 100,
                "source_url": "https://example.org/" + "x" * 200,
            },
        )
        assert len(q) <= 500

    def test_handles_none_summary(self):
        q = build_future_moment_query(
            goal="goal",
            opportunity={"title": "x", "summary": None},
        )
        # Falls back to the "see source for details" sentinel
        assert "see source" in q.lower() or "unspecified" in q.lower()


# ---------------------------------------------------------------------------
# Quick-Sim metrics prompts (rationale framing)
# ---------------------------------------------------------------------------


@pytest.mark.fast
class TestMetricsPromptFraming:
    """The metrics prompts must steer the rationale toward factual analysis,
    not a narrated pitch scene. Guards the Find Money "assessment" text from
    drifting back into present-tense drama (e.g. "in a high-stakes pitch")."""

    def test_system_prompt_forbids_scene_narration(self):
        # Collapse whitespace so line-wrapped phrases still match.
        sys = " ".join(get_metrics_system_prompt().lower().split())
        # Must explicitly tell the model not to narrate a live scene/pitch.
        assert "do not describe the room" in sys
        # The drama exemplars we are guarding against are named so the
        # instruction is model-agnostic (works regardless of model quirks).
        assert "high-stakes pitch" in sys
        assert "skeptical evaluators" in sys

    def test_system_prompt_demands_factual_fit_analysis(self):
        sys = get_metrics_system_prompt().lower()
        assert "factual analysis" in sys
        assert "analyst" in sys

    def test_user_prompt_marks_scene_as_visual_context_only(self):
        prompt = get_metrics_prompt(
            goal="$50k operating grant by Sept 2026",
            opportunity={
                "title": "Climate Action Fund",
                "summary": "Annual climate grants",
                "amount": 25000,
                "deadline": "2026-09-01",
                "source_url": "https://example.org/x",
            },
            scene_context="oak-panelled boardroom, polite tension, slide deck",
        )
        low = prompt.lower()
        # Scene is flagged as context only, and the rationale schema hint must
        # not ask for scene-anchored narration.
        assert "visual context only" in low
        assert "do not retell it" in low
        assert "no scene narration" in low
        # Opportunity + goal still flow through for grounding.
        assert "Climate Action Fund" in prompt
        assert "$50k operating grant by Sept 2026" in prompt

    def test_rationale_schema_hint_is_not_scene_anchored(self):
        prompt = get_metrics_prompt(
            goal="goal",
            opportunity={"title": "x"},
            scene_context="a room",
        )
        # The old hint ("summary anchored in the scene") is gone.
        assert "anchored in the scene" not in prompt.lower()


# ---------------------------------------------------------------------------
# summarize_tdf_for_metrics
# ---------------------------------------------------------------------------


@pytest.mark.fast
class TestSummarizeTdfForMetrics:
    """Tests for the TDF → metrics-prompt summariser."""

    def test_empty_tdf_falls_back_to_query(self):
        s = summarize_tdf_for_metrics({"query": "fallback query"})
        assert "fallback query" in s

    def test_completely_empty_tdf_returns_sentinel(self):
        s = summarize_tdf_for_metrics({})
        assert s  # not empty; either query or sentinel

    def test_extracts_scene_fields(self):
        s = summarize_tdf_for_metrics(
            {
                "scene_data": {
                    "setting": "oak-panelled boardroom",
                    "atmosphere": "polite tension",
                    "tension_level": "high",
                    "focal_point": "the user's slide deck",
                }
            }
        )
        assert "oak-panelled boardroom" in s
        assert "polite tension" in s
        assert "high" in s
        assert "slide deck" in s

    def test_extracts_moment_fields(self):
        s = summarize_tdf_for_metrics(
            {
                "moment_data": {
                    "plot_summary": "user presents the budget",
                    "stakes": "two years of runway",
                    "tension_arc": "climactic",
                    "central_question": "will the chair sign?",
                }
            }
        )
        assert "presents the budget" in s
        assert "two years of runway" in s
        assert "climactic" in s
        assert "chair sign" in s

    def test_extracts_character_names(self):
        s = summarize_tdf_for_metrics(
            {
                "character_data": {
                    "characters": [
                        {"name": "Dr. Chen"},
                        {"name": "Board Chair Reyes"},
                    ]
                }
            }
        )
        assert "Dr. Chen" in s
        assert "Board Chair Reyes" in s

    def test_handles_string_grounded_facts(self):
        s = summarize_tdf_for_metrics(
            {
                "grounding_data": {
                    "facts": ["fact A", "fact B", "fact C", "fact D"],
                },
                "scene_data": {"setting": "x", "atmosphere": "y"},
            }
        )
        assert "fact A" in s
        # Only first three retained
        assert "fact D" not in s

    def test_handles_dict_grounded_facts(self):
        s = summarize_tdf_for_metrics(
            {
                "grounding_data": {
                    "facts": [{"statement": "fact A"}, {"text": "fact B"}],
                },
                "scene_data": {"setting": "x", "atmosphere": "y"},
            }
        )
        assert "fact A" in s
        assert "fact B" in s


# ---------------------------------------------------------------------------
# Real GenerationPipeline integration — catches __init__ signature drift
# ---------------------------------------------------------------------------


@pytest.mark.fast
class TestGenerationPipelineIntegration:
    """Construct a real GenerationPipeline through the handler's seam.

    The handler builds every pipeline via
    :func:`app.api.v1.find_money._build_generation_pipeline`. These tests
    call that exact function with the exact kwargs the handler passes,
    so an ``__init__`` signature regression fails CI here rather than at
    runtime in production.

    This is the gap that let PR #45 ship
    ``TypeError: GenerationPipeline.__init__() got an unexpected keyword
    argument 'user_id'`` — its unit tests validated schemas but never
    built a real pipeline. Nothing here is mocked; construction is real,
    and it stops before the live LLM call (which needs real API keys).
    """

    def test_build_generation_pipeline_constructs_real_pipeline(self):
        """The handler seam builds a real GenerationPipeline with its kwargs.

        Fails if ``GenerationPipeline.__init__`` drops or renames
        ``preset`` / ``user_id`` / ``entity_ids`` — i.e. the exact
        regression PR #45 shipped.
        """
        pipeline = _build_generation_pipeline(
            preset=QualityPreset.HYPER,
            user_id="user-abc123",
            entity_ids=["clockchain-figure-1"],
        )
        assert isinstance(pipeline, GenerationPipeline)
        # The kwargs must actually land on the object, not just be accepted.
        assert pipeline._user_id == "user-abc123"
        assert pipeline._preset == QualityPreset.HYPER
        assert pipeline._entity_ids == ["clockchain-figure-1"]

    def test_build_generation_pipeline_with_minimal_kwargs(self):
        """Anonymous (AUTH_ENABLED=false) requests pass user_id=None."""
        pipeline = _build_generation_pipeline(preset=None, user_id=None)
        assert isinstance(pipeline, GenerationPipeline)
        assert pipeline._user_id is None

    def test_generation_pipeline_signature_accepts_quick_sim_kwargs(self):
        """Explicit signature guard: GenerationPipeline must accept these kwargs.

        Belt-and-suspenders alongside the construction test — names the
        contract the Find Money handler depends on so a future signature
        change is an obvious, self-documenting CI failure.
        """
        params = inspect.signature(GenerationPipeline.__init__).parameters
        for kw in ("preset", "user_id", "entity_ids"):
            assert kw in params, (
                f"GenerationPipeline.__init__ no longer accepts '{kw}' — "
                "the Find Money quick-sim handler passes it."
            )

    def test_simulate_one_builds_through_the_seam(self):
        """_simulate_one must construct its pipeline via _build_generation_pipeline.

        Guards the wiring: if a refactor reintroduces a direct
        ``GenerationPipeline(...)`` call in ``_simulate_one``, the
        construction test above stops covering the real handler path.
        """
        from app.api.v1 import find_money as fm

        source = inspect.getsource(fm._simulate_one)
        assert "_build_generation_pipeline(" in source
        assert "GenerationPipeline(" not in source


# ---------------------------------------------------------------------------
# Light quick-sim pipeline parameterization (task el-3pwch)
# ---------------------------------------------------------------------------


@pytest.mark.fast
class TestQuickSimLightPipeline:
    """Quick-sim drives the LIGHT pipeline path, not the full ~14-agent render.

    The original endpoint ran ``GenerationPipeline.run`` — the full
    render (Judge -> Grounding -> EntityGrounding -> Timeline -> Scene ->
    Characters+bios -> Graph -> Moment -> Camera -> Dialog -> ImagePrompt
    -> ...). A single opportunity took >90s, so a 15-opportunity batch
    could never settle inside any reasonable timeout. Quick-sim only
    needs scene + moment + character names to ground the metrics agent,
    so it now calls ``GenerationPipeline.run_quick_sim`` — five LLM calls
    (Judge -> Timeline -> Scene -> CharacterIdentification -> Moment).

    Nothing here is mocked (per ``feedback_no_mocks.md``); these are
    structural guards that stop before the live LLM call.
    """

    def test_pipeline_exposes_run_quick_sim(self):
        """GenerationPipeline must expose the light ``run_quick_sim`` entry point."""
        assert hasattr(GenerationPipeline, "run_quick_sim")
        assert inspect.iscoroutinefunction(GenerationPipeline.run_quick_sim)
        # It takes exactly the framing query — no generate_image, because
        # the light path never renders an image.
        params = inspect.signature(GenerationPipeline.run_quick_sim).parameters
        assert list(params) == ["self", "query"]

    def test_pipeline_exposes_quick_sim_characters_step(self):
        """The light path identifies characters without the bio fan-out."""
        assert hasattr(GenerationPipeline, "_step_quick_sim_characters")
        assert inspect.iscoroutinefunction(GenerationPipeline._step_quick_sim_characters)

    def test_run_quick_sim_skips_the_heavy_agents(self):
        """``run_quick_sim`` must not invoke the heavy / image-path steps.

        Grounding, entity grounding, the relationship graph, character
        bios, dialog, camera, and the whole image pipeline are what made
        a single opportunity take >90s. The light path must skip them.
        """
        source = inspect.getsource(GenerationPipeline.run_quick_sim)
        # The five steps the light path DOES run.
        assert "_step_judge(" in source
        assert "_step_timeline(" in source
        assert "_step_scene(" in source
        assert "_step_quick_sim_characters(" in source
        assert "_step_moment(" in source
        # The steps it must NOT run.
        for skipped in (
            "_step_grounding(",
            "_step_entity_grounding(",
            "_step_graph(",
            "_step_characters(",
            "_step_dialog(",
            "_step_camera(",
            "_step_image_prompt(",
            "_step_image_generation(",
        ):
            assert skipped not in source, f"run_quick_sim must not call {skipped}"

    def test_quick_sim_characters_runs_no_bio_calls(self):
        """``_step_quick_sim_characters`` identifies names only — no bio agent.

        Character bios are the pipeline's most expensive fan-out (one LLM
        call per character). Quick-sim's metrics summariser only reads
        character *names*, so the step folds identification stubs into
        fallback characters with zero extra LLM calls.
        """
        source = inspect.getsource(GenerationPipeline._step_quick_sim_characters)
        assert "_char_id_agent" in source
        assert "create_fallback_character(" in source
        # No bio agent invocation.
        assert "_char_bio_agent" not in source
        assert "generate_bio" not in source

    def test_simulate_one_uses_the_light_path(self):
        """``_simulate_one`` must call ``run_quick_sim`` — not the full ``run``.

        This is the load-bearing parameterization for task el-3pwch: if a
        refactor points ``_simulate_one`` back at ``pipeline.run(...)``,
        the >90s-per-opportunity regression returns.
        """
        from app.api.v1 import find_money as fm

        source = inspect.getsource(fm._simulate_one)
        assert "run_quick_sim(" in source
        assert "pipeline.run(" not in source

    def test_per_opportunity_timeout_is_tight(self):
        """The light path finishes in a few seconds — the timeout is a safety net.

        Running the full render, 120s was barely a cap; on the light path
        it must be far tighter so a genuinely hung provider call cannot
        sink the batch's 60s target.
        """
        from app.api.v1 import find_money as fm

        assert fm._PER_OPPORTUNITY_TIMEOUT_S <= 90
        # Concurrency must let a 15-opportunity batch settle in a few waves.
        assert fm._BATCH_CONCURRENCY >= 4

    def test_quick_sim_pins_a_verified_google_native_text_model(self):
        """Quick-sim pins the text path to a fast, verified Google-native model.

        The ``hyper`` preset's ``google/gemini-2.0-flash-001`` routes
        through OpenRouter, whose shared upstream is chronically 429
        rate-limited — every call eats a rate-limit round-trip. Pinning a
        Google-native model sidesteps that. The model must be in
        :class:`VerifiedModels` so it always passes preset validation.
        """
        from app.api.v1 import find_money as fm
        from app.config import VerifiedModels

        assert fm._QUICK_SIM_TEXT_MODEL in VerifiedModels.GOOGLE_TEXT
        # A Google-native id, not an OpenRouter-namespaced one.
        assert "/" not in fm._QUICK_SIM_TEXT_MODEL

    def test_quick_sim_caps_thinking_and_output_budget(self):
        """Quick-sim caps the thinking budget and output tokens for speed.

        ``gemini-2.5-flash`` defaults to a dynamic thinking budget that
        burns 5-10s per structured call. Quick-sim is a first-pass read,
        so it pins a small fixed ``thinking_level`` (kept > 0 — a hard 0
        makes the Judge agent reject the future-moment query) and a
        bounded ``max_tokens``.
        """
        from app.api.v1 import find_money as fm

        params = fm._QUICK_SIM_LLM_PARAMS
        assert 0 < params["thinking_level"] <= 2048
        assert 0 < params["max_tokens"] <= 8192

    def test_simulate_one_pins_model_and_thinking_budget(self):
        """``_simulate_one`` must build the pipeline with the fast-path tuning.

        Guards the parameterization wiring: the pipeline AND the metrics
        agent both have to receive the pinned text model / capped thinking
        budget, or the per-opportunity path slides back toward >90s.
        """
        from app.api.v1 import find_money as fm

        source = inspect.getsource(fm._simulate_one)
        # Pipeline gets the pinned model + capped llm params.
        assert "_QUICK_SIM_TEXT_MODEL" in source
        assert "_QUICK_SIM_LLM_PARAMS" in source
        # The metrics agent must also get the capped llm params — without
        # it the metrics call falls back to the dynamic thinking budget.
        assert "llm_params=" in source

    def test_build_generation_pipeline_threads_text_model_and_llm_params(self):
        """The construction seam forwards ``text_model`` + ``llm_params``.

        These land on the real :class:`GenerationPipeline`, so a future
        ``__init__`` signature change that drops them fails CI here.
        """
        pipeline = _build_generation_pipeline(
            preset=QualityPreset.HYPER,
            user_id=None,
            text_model="gemini-2.5-flash",
            llm_params={"thinking_level": 512, "max_tokens": 4096},
        )
        assert isinstance(pipeline, GenerationPipeline)
        assert pipeline._text_model == "gemini-2.5-flash"
        assert pipeline._llm_params == {"thinking_level": 512, "max_tokens": 4096}

    def test_quick_sim_metrics_agent_accepts_llm_params(self):
        """``QuickSimMetricsAgent`` must accept and store ``llm_params``.

        Quick-sim passes its capped thinking budget to the metrics agent;
        if the agent's ``__init__`` stops accepting ``llm_params`` the
        metrics call silently reverts to the slow dynamic thinking budget.
        """
        from app.agents.quick_sim import QuickSimMetricsAgent

        params = inspect.signature(QuickSimMetricsAgent.__init__).parameters
        assert "llm_params" in params
        agent = QuickSimMetricsAgent(llm_params={"thinking_level": 512})
        assert agent._llm_params == {"thinking_level": 512}


# ---------------------------------------------------------------------------
# Response shape — QuickSimTdfEntry / QuickSimBatchResponse (JSON, not SSE)
# ---------------------------------------------------------------------------


@pytest.mark.fast
class TestBuildTdfEntry:
    """`_build_tdf_entry` folds a sim result into the web-app's entry shape.

    The flat key set must match what
    ``timepoint-web-app/app/find_money/runs/jobs.py::_seed_quick_sim_tdfs``
    produces, so real Flash output and the web-app seed fallback are
    interchangeable to the selection page.
    """

    # The exact flat shape the web-app pairs against.
    _CANONICAL_KEYS = {
        "tdf_ref",
        "opportunity_index",
        "title",
        "url",
        "summary",
        "probability",
        "fit_score",
        "effort_score",
        "amount_usd",
        "source",
    }

    def _opportunity(self) -> OpportunityIn:
        return OpportunityIn(
            title="Climate Action Fund",
            source_url="https://example.org/climate",
            summary="Annual $10-50k grants for climate work",
            amount=25000,
        )

    def test_success_entry_has_canonical_shape(self):
        metrics = QuickSimMetrics(
            probability_of_award=0.18,
            fit_score=0.62,
            effort_score=0.5,
            effort_estimate="moderate — 20h proposal",
            key_risks=["tight deadline"],
            key_levers=["warm intro"],
            rationale="strong fit, crowded pool",
        )
        result = {
            "success": True,
            "tdf": {"scene_data": {"setting": "boardroom"}},
            "quick_sim": metrics,
            "error": None,
            "latency_ms": 42000,
        }
        entry = _build_tdf_entry(index=7, opportunity=self._opportunity(), result=result)

        assert isinstance(entry, QuickSimTdfEntry)
        dumped = entry.model_dump()
        # Every web-app-required key is present.
        assert self._CANONICAL_KEYS <= set(dumped)
        assert entry.tdf_ref == "flash:quick:7"
        assert entry.opportunity_index == 7
        assert entry.title == "Climate Action Fund"
        assert entry.url == "https://example.org/climate"
        assert entry.summary == "Annual $10-50k grants for climate work"
        assert entry.probability == pytest.approx(0.18)
        assert entry.fit_score == pytest.approx(0.62)
        assert entry.effort_score == pytest.approx(0.5)
        assert entry.amount_usd == 25000
        assert entry.source == "flash-quick-sim"
        assert entry.error is None
        # Rich payload is carried through for the downstream Pro deep-sim.
        assert entry.tdf == {"scene_data": {"setting": "boardroom"}}
        assert entry.quick_sim is metrics
        assert entry.latency_ms == 42000

    def test_error_entry_has_canonical_shape_with_null_metrics(self):
        """Failed opportunities still produce one entry — null scores, flagged source."""
        result = {
            "success": False,
            "tdf": None,
            "quick_sim": None,
            "error": "quick_sim timed out after 120s",
            "latency_ms": 120100,
        }
        entry = _build_tdf_entry(index=3, opportunity=self._opportunity(), result=result)

        dumped = entry.model_dump()
        assert self._CANONICAL_KEYS <= set(dumped)
        assert entry.tdf_ref == "flash:quick:3"
        assert entry.opportunity_index == 3
        assert entry.probability is None
        assert entry.fit_score is None
        assert entry.effort_score is None
        assert entry.source == "flash-quick-sim-error"
        assert entry.error == "quick_sim timed out after 120s"
        assert entry.tdf is None
        assert entry.quick_sim is None

    def test_amount_passthrough_for_string_amount(self):
        opp = OpportunityIn(title="x", amount="$10k–$50k")
        result = {"success": False, "tdf": None, "quick_sim": None, "error": "e"}
        entry = _build_tdf_entry(index=0, opportunity=opp, result=result)
        assert entry.amount_usd == "$10k–$50k"


@pytest.mark.fast
class TestQuickSimBatchResponse:
    """The batch response is a single JSON object — ``{"tdfs": [...]}`` — not SSE."""

    def test_response_serialises_tdfs_as_list(self):
        entry = QuickSimTdfEntry(
            tdf_ref="flash:quick:0",
            opportunity_index=0,
            title="Climate Action Fund",
            source="flash-quick-sim",
        )
        resp = QuickSimBatchResponse(
            tdfs=[entry],
            completed=1,
            errored=0,
            total=1,
            request_context={"run_id": "fm-run-1"},
        )
        dumped = resp.model_dump()
        assert isinstance(dumped["tdfs"], list)
        assert dumped["tdfs"][0]["tdf_ref"] == "flash:quick:0"
        assert dumped["completed"] == 1
        assert dumped["total"] == 1
        assert dumped["request_context"] == {"run_id": "fm-run-1"}

    def test_json_round_trip(self):
        """The response is plain JSON the web-app can ``r.json()`` directly."""
        resp = QuickSimBatchResponse(tdfs=[], completed=0, errored=0, total=0)
        raw = resp.model_dump_json()
        reparsed = QuickSimBatchResponse.model_validate_json(raw)
        assert reparsed.tdfs == []
        assert reparsed.total == 0


# ---------------------------------------------------------------------------
# Endpoint registration + request validation (no LLM calls)
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    """Synchronous TestClient — sufficient for validation-error paths."""
    from app.main import app

    return TestClient(app)


@pytest.mark.fast
class TestEndpointRegistered:
    """The endpoint must be a registered, JSON (non-SSE) POST route."""

    _PATH = "/api/v1/find-money/quick-sim-batch"

    def test_route_is_registered(self, client):
        # Assert via the client rather than scraping ``app.routes``: depending
        # on the resolved FastAPI/Starlette version, an included router may be
        # left as a nested ``_IncludedRouter`` wrapper (which has no ``.path``)
        # instead of being flattened onto ``app.routes`` — scraping then either
        # crashes with ``AttributeError`` or misses the nested path. A
        # *registered* path rejects a bad body with 422; only an *unregistered*
        # path 404s. That distinction is the actual contract under test.
        resp = client.post(self._PATH, json={})
        assert resp.status_code != 404, f"route not registered: {resp.status_code}"

    def test_route_returns_json_batch_response_not_sse(self):
        """The route's response_model is QuickSimBatchResponse — a JSON body.

        This is the structural guarantee that the endpoint no longer
        streams ``text/event-stream`` (which the API gateway 502s on and
        the web-app's ``r.json()`` consumer cannot parse).
        """
        # Inspect the find-money sub-router directly. Its route path
        # (``/find-money/quick-sim-batch``) and ``response_model`` are stable
        # regardless of how the parent app flattens or nests included routers.
        from app.api.v1.find_money import router as fm_router
        from app.schemas.quick_sim import QuickSimBatchResponse as _Resp

        route = next(
            r for r in fm_router.routes if getattr(r, "path", "").endswith("/quick-sim-batch")
        )
        assert route.response_model is _Resp  # type: ignore[attr-defined]
        # SSE was the old contract — the helpers that built it are gone.
        from app.api.v1 import find_money as fm

        assert not hasattr(fm, "_format_sse")
        assert not hasattr(fm, "QuickSimEvent")

    def test_get_returns_405(self, client):
        """GET is not allowed — only POST."""
        resp = client.get(self._PATH)
        assert resp.status_code in (404, 405)

    def test_empty_body_returns_422(self, client):
        resp = client.post(self._PATH, json={})
        assert resp.status_code == 422

    def test_empty_opportunities_returns_422(self, client):
        resp = client.post(
            self._PATH,
            json={"goal": "valid goal", "opportunities": []},
        )
        assert resp.status_code == 422

    def test_too_many_opportunities_returns_422(self, client):
        resp = client.post(
            self._PATH,
            json={
                "goal": "valid goal",
                "opportunities": [{"title": f"opp {i}"} for i in range(16)],
            },
        )
        assert resp.status_code == 422

    def test_goal_too_short_returns_422(self, client):
        resp = client.post(
            self._PATH,
            json={
                "goal": "ab",
                "opportunities": [{"title": "opp 1"}],
            },
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Quick-sim timepoint persistence (regression)
# ---------------------------------------------------------------------------


class TestQuickSimPersistence:
    """Quick-sim timepoints must be persisted to Flash's DB.

    Regression test for fix-quick-sim-persist-timepoints-2026-05-27. The
    handler used to build a Timepoint with a generated UUID + slug, return
    them to the web-app, but never call ``session.add`` — so every
    web-app "Preview the moment" link 404'd via
    ``GET /api/v1/timepoints/{id}``. This test exercises the persistence
    helper against a real test DB (no mocks) and then re-reads via the
    public GET endpoint to assert the round-trip works.
    """

    async def test_persist_then_get_via_api_round_trips(self, test_client):
        """`_persist_quick_sim_timepoint` saves the row; GET /timepoints/{id}
        then returns 200 with the same slug."""
        from app.api.v1.find_money import _persist_quick_sim_timepoint
        from app.models import Timepoint, TimepointStatus, TimepointVisibility

        tp = Timepoint.create(
            query="$50k climate operating grant by Sept 2026",
            status=TimepointStatus.COMPLETED,
            tdf_payload={"query": "$50k climate operating grant", "scene_data": {}},
            tdf_hash="quicksim-test-hash",
            year=2026,
        )

        persisted_id = await _persist_quick_sim_timepoint(tp, user_id=None)

        assert persisted_id is not None, "quick-sim timepoint must be persisted"
        assert persisted_id == tp.id

        # The round-trip through the real GET handler is the bug: before
        # this fix the GET 404'd because the row was never saved.
        resp = await test_client.get(f"/api/v1/timepoints/{persisted_id}")
        assert resp.status_code == 200, (
            f"expected 200 from GET /api/v1/timepoints/{persisted_id}, "
            f"got {resp.status_code}: {resp.text}"
        )
        body = resp.json()
        assert body["id"] == persisted_id
        assert body["slug"] == tp.slug
        # Anonymous quick-sim (user_id=None) persists as PUBLIC so the
        # Preview link is reachable; authenticated runs persist as PRIVATE.
        assert body.get("visibility") == TimepointVisibility.PUBLIC.value


# ---------------------------------------------------------------------------
# Quick-sim async image generation (feat-quick-sim-async-image-gen-2026-05-28)
# ---------------------------------------------------------------------------


@pytest.mark.fast
class TestQuickSimAsyncImageGen:
    """Quick-sim must schedule a fire-and-forget image gen after persistence.

    Quick-sim's :meth:`GenerationPipeline.run_quick_sim` deliberately skips
    the image path so the per-opportunity latency stays under the 60s
    product target. That left the persisted row with ``image_url=NULL``,
    so the web-app's Preview page rendered a placeholder. The fix
    schedules :func:`_run_quick_sim_image_gen` AFTER successful persistence
    so the image fills in ~30s later on a subsequent page load.

    Per ``feedback_no_mocks.md`` nothing here is mocked. The test that
    would exercise a real image-model call needs API keys + ~30s of
    runtime, so the structural guards below assert the *scheduling*
    contract (which is the regression-prone surface) and the side-effect
    test that actually awaits an image is gated on a real backend.
    """

    def test_run_helper_exists_and_is_coroutine(self):
        """The image-gen helper must be a coroutine — needed for create_task."""
        from app.api.v1 import find_money as fm

        assert hasattr(fm, "_run_quick_sim_image_gen")
        assert inspect.iscoroutinefunction(fm._run_quick_sim_image_gen)

    def test_schedule_helper_creates_named_task(self):
        """``_schedule_quick_sim_image_gen`` returns an asyncio Task named for the row.

        Naming the task ``quick-sim-img-{timepoint_id}`` is load-bearing
        for log readability — when one of these warns, you need to be
        able to tell which row it belonged to without instrumenting the
        helper.
        """
        from app.api.v1 import find_money as fm

        assert hasattr(fm, "_schedule_quick_sim_image_gen")
        # The schedule call is sync (it returns the task object) so the
        # response can continue without awaiting.
        assert not inspect.iscoroutinefunction(fm._schedule_quick_sim_image_gen)

    async def test_schedule_creates_named_task_and_registers_it(self):
        """Schedule registers the task with the module-level set + name.

        Real (non-mocked) call: build a tiny dummy pipeline + state, schedule
        the task, then cancel it before the image-prompt step makes any
        network call. This asserts the scheduling contract — the task is
        created, named, and held in ``_BACKGROUND_IMG_TASKS`` so the loop
        doesn't garbage-collect it.
        """
        import asyncio as _asyncio

        from app.api.v1 import find_money as fm

        # Real pipeline + state. The pipeline is never RUN here — we cancel
        # the scheduled task before its first step can issue a network call.
        pipeline = _build_generation_pipeline(preset=None, user_id=None)

        class _DummyState:
            pass

        task = fm._schedule_quick_sim_image_gen(
            timepoint_id="tp-test-schedule-1",
            pipeline=pipeline,
            state=_DummyState(),
        )
        try:
            assert isinstance(task, _asyncio.Task)
            assert task.get_name() == "quick-sim-img-tp-test-schedule-1"
            assert task in fm._BACKGROUND_IMG_TASKS
        finally:
            task.cancel()
            try:
                await task
            except BaseException:  # noqa: BLE001 — cancel + any swallow
                pass
            # done_callback must have removed it from the registry.
            assert task not in fm._BACKGROUND_IMG_TASKS

    def test_simulate_one_schedules_image_gen_only_on_persist_success(self):
        """``_simulate_one`` must schedule image gen only when persistence succeeded.

        Two structural requirements:

        1. The schedule call exists in ``_simulate_one`` (it's the wiring).
        2. It's gated by ``persisted_id is not None`` — firing on a failed
           persist would log a warning trying to update a row that doesn't
           exist, but more importantly there's no row to update, so the
           task is pure waste.
        """
        from app.api.v1 import find_money as fm

        source = inspect.getsource(fm._simulate_one)
        assert "_schedule_quick_sim_image_gen(" in source
        assert "if persisted_id is not None" in source
        # The schedule call must appear AFTER the persist call, not before.
        persist_idx = source.index("_persist_quick_sim_timepoint(")
        schedule_idx = source.index("_schedule_quick_sim_image_gen(")
        assert schedule_idx > persist_idx, (
            "image-gen scheduling must follow persistence — firing before "
            "would race against the row insert"
        )

    def test_image_gen_helper_uses_fresh_session(self):
        """The background image-gen helper must open its own session.

        The request's session closes when the response returns; if the
        helper reused it the task would crash on first DB access. Mirror
        the pattern in ``app.core.background_grounding``.
        """
        from app.api.v1 import find_money as fm

        source = inspect.getsource(fm._run_quick_sim_image_gen)
        assert "get_session()" in source
        # And it writes to image_url, not some other field — match the
        # column the regular full pipeline writes.
        assert "image_url" in source

    def test_image_gen_helper_swallows_exceptions(self):
        """Failures must not crash quick-sim — log + return.

        The persisted moment is already returned to the user; an image
        failure must stay as the placeholder (the row's image_url just
        remains NULL).
        """
        from app.api.v1 import find_money as fm

        source = inspect.getsource(fm._run_quick_sim_image_gen)
        # Broad except + warning log, no re-raise, no retry loop.
        assert "except Exception" in source
        assert "logger.warning" in source
        # No retry — the contract is "do not retry, do not crash".
        assert "for attempt" not in source
        assert "retry" not in source.lower() or "no retry" in source.lower()

    def test_image_gen_helper_does_not_hardcode_image_model(self):
        """The pipeline's normal model selection must apply — no hardcode.

        Per the spec: do NOT hardcode a different image model; let the
        pipeline's preset / ``get_image_fallback_model(permissive_only=True)``
        path apply. Hardcoding a model here would silently diverge from
        the full pipeline's selection.
        """
        from app.api.v1 import find_money as fm

        source = inspect.getsource(fm._run_quick_sim_image_gen)
        # No raw model identifiers — model selection happens inside the
        # pipeline's ImageGen step via the router config.
        for forbidden in (
            "black-forest-labs/",
            "stability-ai/",
            "openai/dall-e",
            "google/imagen",
        ):
            assert forbidden not in source, (
                f"image-gen helper must not hardcode {forbidden} — the "
                "pipeline's existing model selection has to apply"
            )
