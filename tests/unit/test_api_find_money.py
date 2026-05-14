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
    _build_generation_pipeline,
    _build_tdf_entry,
    summarize_tdf_for_metrics,
)
from app.config import QualityPreset
from app.core.pipeline import GenerationPipeline
from app.prompts.quick_sim import build_future_moment_query
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

    def test_route_is_registered(self):
        from app.main import app

        paths = {r.path for r in app.routes}  # type: ignore[attr-defined]
        # FastAPI's APIRouter combines parent prefix with the route path.
        assert self._PATH in paths

    def test_route_returns_json_batch_response_not_sse(self):
        """The route's response_model is QuickSimBatchResponse — a JSON body.

        This is the structural guarantee that the endpoint no longer
        streams ``text/event-stream`` (which the API gateway 502s on and
        the web-app's ``r.json()`` consumer cannot parse).
        """
        from app.main import app
        from app.schemas.quick_sim import QuickSimBatchResponse as _Resp

        route = next(
            r
            for r in app.routes
            if getattr(r, "path", None) == self._PATH  # type: ignore[attr-defined]
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
