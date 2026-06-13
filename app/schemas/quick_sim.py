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

from enum import Enum
from typing import Any

from pydantic import AliasChoices, BaseModel, Field


class ConfidenceBasis(str, Enum):
    """Where a :class:`QuickSimMetrics` score's confidence comes from.

    Fail-closed scoring discipline: a breadth-tier quick-sim score that
    cannot be honestly grounded in the run must be *flagged*, never
    fabricated as a confident mid-range number. ``insufficient_evidence``
    is that flag — it tells the selection page to down-rank the entry
    rather than mix it in at face value.

    Members:
        GROUNDED: Anchored in real opportunity facts AND a usable scene.
        INFERRED: Reasoned from partial signal; some fields were missing.
        INSUFFICIENT_EVIDENCE: Nothing real to anchor on — the scores are
            not trustworthy. Forced by :func:`apply_confidence_floor` when
            the inputs are empty/no-op, regardless of the model's self-report.
    """

    GROUNDED = "grounded"
    INFERRED = "inferred"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


# Default self-reported confidence when the model omits the field (additive
# contract: older callers that never sent score_confidence still parse).
DEFAULT_SCORE_CONFIDENCE = 0.5

# Hard cap applied to score_confidence when the deterministic post-check
# decides the inputs cannot support a grounded assessment. Kept low so the
# selection page reliably sorts these below grounded/inferred entries; this is
# NOT a fabricated mid-range fill — it is an explicit "do not trust" flag that
# travels with confidence_basis == insufficient_evidence.
INSUFFICIENT_EVIDENCE_CONFIDENCE_CAP = 0.1

# The two no-op fallback strings emitted by
# ``find_money.py::summarize_tdf_for_metrics`` when the scene pipeline
# produced nothing usable. A scene_context equal to either of these carries no
# real signal, so the metrics call had nothing to anchor on.
NO_OP_SCENE_CONTEXTS = frozenset(
    {
        "(no scene context available)",
        "(scene pipeline returned no usable summary)",
    }
)


class OpportunityIn(BaseModel):
    """A single opportunity stub fed into Quick-Sim.

    Mirrors the shape produced by the Find Money web-search step. All
    fields except ``title`` are optional — the LLM is robust to missing
    data, and the caller may have varying-quality results.

    The web-app sourcing stage (``app/find_money/runs/jobs.py``) emits
    opportunity stubs keyed ``url`` / ``amount_usd``; this endpoint's
    own spec uses ``source_url`` / ``amount``. Both spellings are
    accepted on input via validation aliases so the cross-service
    contract works regardless of which side names the field.

    Attributes:
        title: Short opportunity name (required).
        source_url: Canonical URL for the opportunity (optional).
            Accepts ``url`` as an alias.
        summary: Short prose description (optional).
        amount: Dollar amount available, as a number or human string
            ("$10k–$50k", "up to $25,000", 50000). Accepts ``amount_usd``
            as an alias.
        deadline: Application/award deadline as ISO date or human string.
    """

    title: str = Field(..., min_length=1, max_length=300)
    source_url: str | None = Field(
        default=None,
        max_length=2000,
        validation_alias=AliasChoices("source_url", "url"),
    )
    summary: str | None = Field(default=None, max_length=4000)
    amount: float | int | str | None = Field(
        default=None,
        validation_alias=AliasChoices("amount", "amount_usd"),
    )
    deadline: str | None = Field(default=None, max_length=200)


class QuickSimBatchRequest(BaseModel):
    """Request body for POST /api/v1/find-money/quick-sim-batch.

    Attributes:
        goal: Free-text user goal (e.g. "$50k operating grant by Sept 2026").
        opportunities: 1–15 opportunity stubs to simulate.
        preset: Quality preset forwarded to the generation pipeline
            (default ``"hyper"`` — batch latency dominates UX, so we
            favour speed by default).
        depth: Operation Control Surface dial value (``fast`` / ``standard`` /
            ``deep`` / ``frontier``). When present, overrides the text and
            judge model used by both the quick-sim render
            (:meth:`GenerationPipeline.run_quick_sim`) and the
            :class:`QuickSimMetricsAgent`, mapping::

                fast     → gemini-2.0-flash (bulk/cheap)
                standard → gemini-2.5-flash (current default, no change)
                deep     → gemini-2.5-flash (same text model as standard; HD image in full render)
                frontier → anthropic/claude-opus-4 (true frontier, Anthropic-direct routing)

            Absent or ``None`` → today's default (``gemini-2.5-flash``), no regression.
            The thinking-budget cap (``thinking_level=512``) is kept for Gemini thinking models
            and naturally ignored by non-thinking providers (OpenRouter/Claude).
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
    depth: str | None = Field(
        default=None,
        description=(
            "Operation Control Surface dial: fast|standard|deep|frontier. "
            "Selects the text/judge model for quick-sim render + metrics agent. "
            "Absent → gemini-2.5-flash default (no regression)."
        ),
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
        effort_score: Normalised effort to pursue this opportunity (0–1,
            higher = more work). 0.0–0.3 is a light-touch application,
            0.4–0.6 a moderate proposal, 0.7–1.0 a heavy full submission.
            The web-app selection page ranks on this numeric field.
        effort_estimate: Short prose estimate of work required
            ("low — 4h application", "high — 60h proposal + budget").
        key_risks: 1–5 short risk bullets (selection criteria, timing,
            opportunity-cost, capacity gaps).
        key_levers: 1–5 short lever bullets — concrete moves that
            materially raise the probability of award.
        rationale: One-sentence summary of why these numbers, anchored
            in the future-moment scene.
        score_confidence: How much the three 0–1 scores can be trusted
            (0–1). Fail-closed discipline: the model self-reports this,
            but the deterministic post-check
            (:func:`apply_confidence_floor`) can only ever *lower* it —
            never raise it past what the inputs actually support. A
            no-signal assessment must NOT emit a confident mid-range
            number; it carries a capped confidence and an
            ``insufficient_evidence`` basis instead.
        confidence_basis: Where the confidence comes from —
            ``grounded`` (anchored in real opportunity facts and a usable
            scene), ``inferred`` (reasoned from partial signal), or
            ``insufficient_evidence`` (nothing real to anchor on; the
            scores are not trustworthy and the selection page should
            down-rank, not face-value-rank, this entry).
    """

    probability_of_award: float = Field(..., ge=0.0, le=1.0)
    fit_score: float = Field(..., ge=0.0, le=1.0)
    effort_score: float = Field(..., ge=0.0, le=1.0)
    effort_estimate: str = Field(..., min_length=1, max_length=500)
    key_risks: list[str] = Field(default_factory=list, max_length=5)
    key_levers: list[str] = Field(default_factory=list, max_length=5)
    rationale: str | None = Field(default=None, max_length=800)
    score_confidence: float = Field(
        default=DEFAULT_SCORE_CONFIDENCE,
        ge=0.0,
        le=1.0,
        description=(
            "Trust in the three scores (0–1). The deterministic post-check "
            "can only lower this, never raise it (fail-closed)."
        ),
    )
    confidence_basis: ConfidenceBasis = Field(
        default=ConfidenceBasis.INFERRED,
        description=(
            "grounded | inferred | insufficient_evidence — never a fabricated mid-range fill."
        ),
    )


def opportunity_has_anchorable_fields(opportunity: dict[str, Any]) -> bool:
    """Return True if an opportunity stub carries any field worth assessing.

    A real fit assessment needs *something* to read: a summary, an amount,
    or a deadline. A stub with none of those three (title-only) gives the
    metrics agent nothing to ground on. ``title`` alone does NOT count —
    every stub has a title, so it carries no discriminating signal.

    Args:
        opportunity: Opportunity stub dict (``summary`` / ``amount`` /
            ``deadline`` / ``title`` / ...). Missing or empty values are
            treated as absent.

    Returns:
        True if at least one of ``summary`` / ``amount`` / ``deadline`` is
        present and non-empty.
    """

    def _present(value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        # Numeric amounts (incl. 0) and other non-string truthy stubs count
        # as present; only None / empty-string are treated as absent.
        return True

    return (
        _present(opportunity.get("summary"))
        or _present(opportunity.get("amount"))
        or _present(opportunity.get("deadline"))
    )


def scene_context_is_no_op(scene_context: str | None) -> bool:
    """Return True if a scene_context is one of the no-op fallback strings.

    ``find_money.py::summarize_tdf_for_metrics`` emits a fixed fallback
    string when the scene pipeline produced nothing usable. Such a context
    gives the metrics agent no real anchor.

    Args:
        scene_context: The scene summary fed to the metrics agent.

    Returns:
        True if the context is empty or exactly one of the known no-op
        fallbacks.
    """
    if not scene_context:
        return True
    stripped = scene_context.strip()
    if not stripped:
        return True
    return stripped in NO_OP_SCENE_CONTEXTS


def apply_confidence_floor(
    metrics: QuickSimMetrics,
    *,
    opportunity: dict[str, Any],
    scene_context: str | None,
) -> QuickSimMetrics:
    """Fail-closed post-check: cap confidence to what the inputs support.

    Pure function (no I/O, no LLM). Inspects the *inputs* the metrics call
    actually had — opportunity-stub completeness and whether the
    ``scene_context`` is a no-op fallback — and **only ever lowers**
    ``score_confidence`` / forces ``confidence_basis``. The model cannot
    talk its way up past what the evidence supports.

    The fail-closed trigger is deliberately strict: when the opportunity
    stub has no anchorable field (no summary AND no amount AND no deadline)
    **and** the scene_context is the no-op fallback, the call had nothing
    real to anchor on. In that case confidence is capped at
    :data:`INSUFFICIENT_EVIDENCE_CONFIDENCE_CAP` and the basis is forced to
    :attr:`ConfidenceBasis.INSUFFICIENT_EVIDENCE`, regardless of what the
    model self-reported. This is the "abstain" path — the entry is kept
    (1:1 pairing preserved) but flagged so the selection page down-ranks it
    rather than mixing a fabricated mid-range number in at face value.

    When evidence IS present, this function never *raises* confidence: it
    leaves the model's self-report intact (PR-01 calibrates whether the
    numbers are right; this PR makes the score honest about its own
    uncertainty). It also clamps any out-of-band self-report and downgrades
    a self-claimed ``grounded`` basis to ``inferred`` when the scene was a
    no-op fallback — a grounded claim with no scene cannot stand.

    Args:
        metrics: The :class:`QuickSimMetrics` the LLM returned.
        opportunity: The opportunity stub the call was run against.
        scene_context: The scene summary fed to the metrics call.

    Returns:
        A new :class:`QuickSimMetrics` with confidence fields adjusted
        downward as needed. The input is not mutated.
    """
    no_anchor = not opportunity_has_anchorable_fields(opportunity)
    no_scene = scene_context_is_no_op(scene_context)

    new_confidence = metrics.score_confidence
    new_basis = metrics.confidence_basis

    if no_anchor and no_scene:
        # Nothing real to anchor on — fail closed. Cap (only lower) and flag.
        new_confidence = min(new_confidence, INSUFFICIENT_EVIDENCE_CONFIDENCE_CAP)
        new_basis = ConfidenceBasis.INSUFFICIENT_EVIDENCE
    elif no_scene and new_basis == ConfidenceBasis.GROUNDED:
        # A "grounded" self-report cannot stand without a usable scene; the
        # opportunity stub still carries signal, so downgrade rather than flag.
        new_basis = ConfidenceBasis.INFERRED

    if new_confidence == metrics.score_confidence and new_basis == metrics.confidence_basis:
        return metrics
    return metrics.model_copy(
        update={"score_confidence": new_confidence, "confidence_basis": new_basis}
    )


class QuickSimTdfEntry(BaseModel):
    """One entry in the quick-sim-batch JSON response — one per opportunity.

    The flat ``tdf_ref`` / ``opportunity_index`` / ``title`` / ``url`` /
    ``summary`` / ``probability`` / ``fit_score`` / ``effort_score`` /
    ``amount_usd`` / ``source`` fields match the shape the web-app's
    Find Money pipeline pairs against (``_seed_quick_sim_tdfs`` in
    ``app/find_money/runs/jobs.py``), so real Flash output and the
    web-app seed fallback are interchangeable to the selection page.

    The richer ``tdf`` / ``quick_sim`` payloads are carried through for
    the downstream Pro deep-sim and result page; the web-app forwards
    each entry dict wholesale, so extra keys are harmless.

    Attributes:
        tdf_ref: Stable per-entry reference (``flash:quick:{index}``).
        opportunity_index: Zero-based index matching request order.
        title: Opportunity title (echoed from the request stub).
        url: Opportunity source URL, if any.
        summary: Opportunity summary, if any.
        probability: ``probability_of_award`` from the metrics agent,
            or ``None`` when the opportunity failed.
        fit_score: ``fit_score`` from the metrics agent, or ``None``.
        effort_score: ``effort_score`` from the metrics agent, or ``None``.
        score_confidence: ``score_confidence`` from the metrics agent
            (after the fail-closed post-check), or ``None`` on failure.
            Mirrored onto the flat entry so the selection page can sort
            without reaching into the nested ``quick_sim`` payload.
        confidence_basis: ``confidence_basis`` from the metrics agent
            (``grounded`` / ``inferred`` / ``insufficient_evidence``), or
            ``None`` on failure. An ``insufficient_evidence`` entry is kept
            in the batch (1:1 pairing) but flagged for down-ranking.
        amount_usd: Opportunity amount (number or free-text), if any.
        source: ``"flash-quick-sim"`` on success,
            ``"flash-quick-sim-error"`` when the opportunity failed.
        tdf: Full future-moment TDF payload (``None`` on failure or when
            the scene pipeline produced nothing).
        quick_sim: Full :class:`QuickSimMetrics` (``None`` on failure).
        error: Failure message (``None`` on success).
        latency_ms: Wall-clock time for this opportunity.
    """

    tdf_ref: str
    opportunity_index: int
    title: str
    url: str | None = None
    summary: str | None = None
    probability: float | None = None
    fit_score: float | None = None
    effort_score: float | None = None
    score_confidence: float | None = None
    confidence_basis: ConfidenceBasis | None = None
    amount_usd: float | int | str | None = None
    source: str
    tdf: dict[str, Any] | None = None
    quick_sim: QuickSimMetrics | None = None
    error: str | None = None
    latency_ms: int = 0


class QuickSimBatchResponse(BaseModel):
    """JSON response body for POST /api/v1/find-money/quick-sim-batch.

    This endpoint returns a single JSON object (HTTP 200), **not** an
    SSE stream — the consumer is a server-side background job
    (``run_quick_sim`` in the web-app), and the API gateway cannot proxy
    ``text/event-stream`` responses.

    Attributes:
        tdfs: One :class:`QuickSimTdfEntry` per requested opportunity,
            ordered by ``opportunity_index``. Includes failed
            opportunities (with ``source == "flash-quick-sim-error"``)
            so the list always pairs 1:1 with the request.
        completed: Count of opportunities that simulated successfully.
        errored: Count of opportunities that failed.
        total: Total opportunities in the request.
        request_context: Opaque context echoed back from the request.
    """

    tdfs: list[QuickSimTdfEntry]
    completed: int
    errored: int
    total: int
    request_context: dict[str, Any] | None = None
