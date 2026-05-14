"""Unit tests for /api/v1/find-money/quick-sim-batch.

These tests cover:
- Request schema validation (size limits, required fields)
- Future-moment query builder (length cap, missing fields handled)
- TDF → metrics-prompt summariser (degrades gracefully)
- SSE format helper
- Endpoint route registration

The pipeline + LLM calls themselves are NOT exercised here (those live
under ``tests/e2e``); per the no-mocks rule we don't fake them. The
endpoint is exercised end-to-end against a live preset in
``tests/e2e/test_find_money_quick_sim.py`` (gated on real API keys).
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.v1.find_money import (
    QuickSimEvent,
    _format_sse,
    summarize_tdf_for_metrics,
)
from app.prompts.quick_sim import build_future_moment_query
from app.schemas.quick_sim import (
    OpportunityIn,
    QuickSimBatchRequest,
    QuickSimMetrics,
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
            effort_estimate="moderate — 20h proposal",
            key_risks=["competitive field"],
            key_levers=["co-applicant from anchor org"],
            rationale="solid fit but crowded competition",
        )
        assert m.probability_of_award == pytest.approx(0.42)
        assert m.fit_score == pytest.approx(0.7)
        assert m.key_risks == ["competitive field"]

    def test_probability_bounds(self):
        with pytest.raises(ValidationError):
            QuickSimMetrics(
                probability_of_award=1.1,
                fit_score=0.5,
                effort_estimate="x",
            )
        with pytest.raises(ValidationError):
            QuickSimMetrics(
                probability_of_award=-0.1,
                fit_score=0.5,
                effort_estimate="x",
            )

    def test_fit_score_bounds(self):
        with pytest.raises(ValidationError):
            QuickSimMetrics(
                probability_of_award=0.5,
                fit_score=1.5,
                effort_estimate="x",
            )

    def test_default_empty_lists(self):
        m = QuickSimMetrics(
            probability_of_award=0.5,
            fit_score=0.5,
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
# SSE format helper
# ---------------------------------------------------------------------------


@pytest.mark.fast
class TestFormatSse:
    """Tests for the SSE wire-format helper."""

    def test_emits_sse_data_line(self):
        line = _format_sse(QuickSimEvent(event="start"))
        assert line.startswith("data: ")
        assert line.endswith("\n\n")

    def test_payload_is_valid_json(self):
        line = _format_sse(
            QuickSimEvent(
                event="opportunity_complete",
                index=0,
                opportunity={"title": "x"},
                data={"latency_ms": 1234},
            )
        )
        # Strip the prefix and trailing newlines, then parse JSON.
        payload = line[len("data: ") :].strip()
        decoded = json.loads(payload)
        assert decoded["event"] == "opportunity_complete"
        assert decoded["index"] == 0
        assert decoded["opportunity"] == {"title": "x"}
        assert decoded["data"]["latency_ms"] == 1234


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
    """The endpoint must be registered under /api/v1/find-money/quick-sim-batch."""

    def test_route_is_registered(self):
        from app.main import app

        paths = {r.path for r in app.routes}  # type: ignore[attr-defined]
        # FastAPI's APIRouter combines parent prefix with the route path.
        assert "/api/v1/find-money/quick-sim-batch" in paths

    def test_get_returns_405(self, client):
        """GET is not allowed — only POST."""
        resp = client.get("/api/v1/find-money/quick-sim-batch")
        assert resp.status_code in (404, 405)

    def test_empty_body_returns_422(self, client):
        resp = client.post("/api/v1/find-money/quick-sim-batch", json={})
        assert resp.status_code == 422

    def test_empty_opportunities_returns_422(self, client):
        resp = client.post(
            "/api/v1/find-money/quick-sim-batch",
            json={"goal": "valid goal", "opportunities": []},
        )
        assert resp.status_code == 422

    def test_too_many_opportunities_returns_422(self, client):
        resp = client.post(
            "/api/v1/find-money/quick-sim-batch",
            json={
                "goal": "valid goal",
                "opportunities": [{"title": f"opp {i}"} for i in range(16)],
            },
        )
        assert resp.status_code == 422

    def test_goal_too_short_returns_422(self, client):
        resp = client.post(
            "/api/v1/find-money/quick-sim-batch",
            json={
                "goal": "ab",
                "opportunities": [{"title": "opp 1"}],
            },
        )
        assert resp.status_code == 422
