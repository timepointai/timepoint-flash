"""Schemas for /api/v1/find-money/quick-sim-batch.

Quick-Sim is a future-tense wrapper over the standard 14-agent pipeline
used by the Find Money workflow. Given a goal and a list of opportunities,
each opportunity is rendered as a future-moment TDF plus a small set of
structured "fit" metrics (probability of award, fit score, effort,
risks, levers).

The schemas here are deliberately permissive — opportunities arrive from
the upstream web-search step which may or may not include all fields.

Examples:
    >>> from app.schemas.quick_sim import OpportunityIn, QuickSimBatchRequest
    >>> req = QuickSimBatchRequest(
    ...     goal="$50k operating grant for a climate non-profit",
    ...     opportunities=[
    ...         OpportunityIn(
    ...             title="Climate Action Fund",
    ...             source_url="https://example.org/climate",
    ...             summary="Annual $10-50k grants for climate work",
    ...             amount=50000,
    ...             deadline="2026-09-01",
    ...         )
    ...     ],
    ... )

Tests:
    - tests/unit/test_schemas_quick_sim.py
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class OpportunityIn(BaseModel):
    """A single opportunity stub fed into Quick-Sim.

    Mirrors the shape produced by the Find Money web-search step. All
    fields except ``title`` are optional — the LLM is robust to missing
    data, and the caller may have varying-quality results.

    Attributes:
        title: Short opportunity name (required).
        source_url: Canonical URL for the opportunity (optional).
        summary: Short prose description (optional).
        amount: Dollar amount available, as a number or human string
            ("$10k–$50k", "up to $25,000", 50000).
        deadline: Application/award deadline as ISO date or human string.
    """

    title: str = Field(..., min_length=1, max_length=300)
    source_url: str | None = Field(default=None, max_length=2000)
    summary: str | None = Field(default=None, max_length=4000)
    amount: float | int | str | None = Field(default=None)
    deadline: str | None = Field(default=None, max_length=200)


class QuickSimBatchRequest(BaseModel):
    """Request body for POST /api/v1/find-money/quick-sim-batch.

    Attributes:
        goal: Free-text user goal (e.g. "$50k operating grant by Sept 2026").
        opportunities: 1–15 opportunity stubs to simulate.
        preset: Quality preset forwarded to the generation pipeline
            (default ``"hyper"`` — batch latency dominates UX, so we
            favour speed by default).
        generate_image: Whether to attach images to the future-moments.
            Default ``False`` — images add ~30s each and aren't needed
            for the decision page.
        request_context: Opaque context passed through to each event.
    """

    goal: str = Field(..., min_length=3, max_length=1000)
    opportunities: list[OpportunityIn] = Field(..., min_length=1, max_length=15)
    preset: str | None = Field(
        default="hyper",
        description="Quality preset forwarded to GenerationPipeline (hyper/balanced/hd).",
    )
    generate_image: bool = Field(
        default=False,
        description="Whether to generate images for the future-moments.",
    )
    request_context: dict[str, Any] | None = Field(
        default=None,
        description="Opaque context echoed back on each SSE event.",
    )


class QuickSimMetrics(BaseModel):
    """Structured fit metrics emitted for each opportunity.

    These are the SNAG-light decision fields the web app surfaces on the
    selection page (top 5 of 15) before the user kicks off the slower
    Pro deep-sim.

    Attributes:
        probability_of_award: Likelihood (0–1) the user wins/secures this
            opportunity if they pursue it.
        fit_score: Alignment (0–1) between the user's goal and what the
            opportunity actually funds.
        effort_estimate: Short prose estimate of work required
            ("low — 4h application", "high — 60h proposal + budget").
        key_risks: 1–5 short risk bullets (selection criteria, timing,
            opportunity-cost, capacity gaps).
        key_levers: 1–5 short lever bullets — concrete moves that
            materially raise the probability of award.
        rationale: One-sentence summary of why these numbers, anchored
            in the future-moment scene.
    """

    probability_of_award: float = Field(..., ge=0.0, le=1.0)
    fit_score: float = Field(..., ge=0.0, le=1.0)
    effort_estimate: str = Field(..., min_length=1, max_length=500)
    key_risks: list[str] = Field(default_factory=list, max_length=5)
    key_levers: list[str] = Field(default_factory=list, max_length=5)
    rationale: str | None = Field(default=None, max_length=800)
