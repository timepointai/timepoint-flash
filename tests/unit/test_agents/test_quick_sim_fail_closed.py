"""Agent-level tests for fail-closed quick-sim scoring (PR-02).

These exercise ``QuickSimMetricsAgent.run`` end to end, stubbing ONLY the
outbound LLM HTTP boundary (``router.call_structured``) — the single
stubbable boundary allowed by repo policy. No real tokens are spent.

The point: even when the model self-reports a confident, grounded score, a
call that had nothing real to anchor on (empty opportunity stub + no-op
scene_context) must come back flagged ``insufficient_evidence`` with a capped
confidence. A valid call is left untouched.
"""

from __future__ import annotations

import pytest

from app.agents.quick_sim import QuickSimMetricsAgent, QuickSimMetricsInput
from app.config import ProviderType
from app.core.providers import LLMResponse
from app.schemas.quick_sim import (
    INSUFFICIENT_EVIDENCE_CONFIDENCE_CAP,
    ConfidenceBasis,
    QuickSimMetrics,
)

NO_OP_SCENE = "(no scene context available)"


class _StubRouter:
    """Stand-in for the LLM router that returns a fixed structured response.

    This stubs the outbound provider HTTP call only — the agent's own
    post-processing (the fail-closed confidence floor) runs for real.
    """

    def __init__(self, content: QuickSimMetrics) -> None:
        self._content = content
        self.calls = 0

    async def call_structured(self, **kwargs):
        self.calls += 1
        return LLMResponse(
            content=self._content,
            raw_response=None,
            model="stub-model",
            provider=ProviderType.GOOGLE,
            usage={"input_tokens": 0, "output_tokens": 0},
            latency_ms=1,
        )


def _confident_grounded() -> QuickSimMetrics:
    # The model claims a confident, grounded score regardless of the inputs.
    return QuickSimMetrics(
        probability_of_award=0.45,
        fit_score=0.55,
        effort_score=0.5,
        effort_estimate="moderate — 20h proposal",
        score_confidence=0.92,
        confidence_basis=ConfidenceBasis.GROUNDED,
    )


@pytest.mark.asyncio
async def test_no_signal_call_is_flagged_insufficient_evidence() -> None:
    router = _StubRouter(_confident_grounded())
    agent = QuickSimMetricsAgent(router=router)  # type: ignore[arg-type]

    result = await agent.run(
        QuickSimMetricsInput(
            goal="$50k operating grant by Sept 2026",
            opportunity={"title": "Bare Opportunity"},  # no summary/amount/deadline
            scene_context=NO_OP_SCENE,
        )
    )

    assert router.calls == 1
    assert result.success
    assert result.content is not None
    # Fail-closed: the confident grounded self-report is overridden.
    assert result.content.confidence_basis == ConfidenceBasis.INSUFFICIENT_EVIDENCE
    assert result.content.score_confidence <= INSUFFICIENT_EVIDENCE_CONFIDENCE_CAP


@pytest.mark.asyncio
async def test_valid_call_keeps_grounded_confidence() -> None:
    router = _StubRouter(_confident_grounded())
    agent = QuickSimMetricsAgent(router=router)  # type: ignore[arg-type]

    result = await agent.run(
        QuickSimMetricsInput(
            goal="$50k operating grant by Sept 2026",
            opportunity={
                "title": "Climate Action Fund",
                "summary": "Annual $10-50k grants for climate work",
                "amount": 50000,
                "deadline": "2026-09-01",
            },
            scene_context="Setting: a tense grant-review boardroom; Stakes: $50k decision",
        )
    )

    assert result.success
    assert result.content is not None
    assert result.content.confidence_basis == ConfidenceBasis.GROUNDED
    assert result.content.score_confidence == pytest.approx(0.92)
