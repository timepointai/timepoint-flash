"""Find Money API endpoints.

Hosts the ``/api/v1/find-money/quick-sim-batch`` endpoint, which renders
1–15 opportunity stubs as future-moment TDFs and returns them as a
single JSON object. The endpoint is consumed by the web app's Find
Money pipeline (``run_quick_sim`` in
``timepoint-web-app/app/find_money/runs/jobs.py``) — a server-side
background job, not a browser, so there is no value in streaming, and
the API gateway cannot proxy ``text/event-stream`` responses.

This module deliberately reuses the existing 14-agent
:class:`app.core.pipeline.GenerationPipeline` for scene generation —
the only new model call is the small :class:`QuickSimMetricsAgent` that
extracts the structured fit fields after each scene completes.

Endpoints:
    POST /api/v1/find-money/quick-sim-batch — batch quick-sim (JSON)

Examples:
    >>> # curl
    >>> POST /api/v1/find-money/quick-sim-batch
    >>> {
    ...   "goal": "$50k operating grant by Sept 2026",
    ...   "opportunities": [
    ...     {"title": "Climate Action Fund", "summary": "..."},
    ...     ...
    ...   ]
    ... }
    >>> # → 200 {"tdfs": [ ...one entry per opportunity... ],
    >>> #         "completed": N, "errored": M, "total": T}

Tests:
    - tests/unit/test_api_find_money.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.quick_sim import QuickSimMetricsAgent, QuickSimMetricsInput
from app.auth.credits import CREDIT_COSTS, grant_credits, spend_credits
from app.auth.dependencies import get_current_user
from app.config import QualityPreset
from app.core.pipeline import GenerationPipeline
from app.database import get_db_session
from app.models_auth import TransactionType, User
from app.schemas.quick_sim import (
    OpportunityIn,
    QuickSimBatchRequest,
    QuickSimBatchResponse,
    QuickSimTdfEntry,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/find-money", tags=["find-money"])


# Per-opportunity credit cost. Keep this tiny — Find Money batches up to 15
# opportunities and a single batch must remain cheap enough that users will
# actually run the discovery step before paying for the slower Pro deep-sim.
# Authoritative cost table lives in app/auth/credits.py CREDIT_COSTS.
_DEFAULT_QUICK_SIM_COST = 2


# Hard wall-clock cap for a single opportunity (scene pipeline + metrics
# agent). The standard generate-stream uses 360s, but we batch up to 15
# of these in a row — keep each tight.
_PER_OPPORTUNITY_TIMEOUT_S = 120

# Concurrency: process opportunities in small chunks so we stay inside
# provider rate limits. The underlying pipeline already manages internal
# parallelism via its own semaphore; we only need to bound how many
# pipelines run at once.
_BATCH_CONCURRENCY = 3


# ---------------------------------------------------------------------------
# GenerationPipeline construction seam
# ---------------------------------------------------------------------------


def _build_generation_pipeline(
    *,
    preset: QualityPreset | None,
    user_id: str | None,
    entity_ids: list[str] | None = None,
) -> GenerationPipeline:
    """Construct the 14-agent pipeline with the kwargs Quick-Sim relies on.

    This is a deliberate, narrow seam: the handler builds every pipeline
    through this one function, so a single real integration test
    (``tests/unit/test_api_find_money.py::TestGenerationPipelineIntegration``)
    can construct a real :class:`GenerationPipeline` here and fail CI on
    an ``__init__`` signature drift.

    PR #45 shipped a runtime crash —
    ``TypeError: GenerationPipeline.__init__() got an unexpected keyword
    argument 'user_id'`` — precisely because its unit tests never built a
    real pipeline. Routing construction through this helper makes that
    class of regression catchable without a live LLM call.

    Args:
        preset: Quality preset forwarded to the pipeline (or ``None``).
        user_id: Authenticated user id, forwarded for entity-visibility
            filtering (``None`` when ``AUTH_ENABLED=false`` / anonymous).
        entity_ids: Optional Clockchain figure ids to pre-populate.

    Returns:
        A ready-to-run :class:`GenerationPipeline`.
    """
    return GenerationPipeline(
        preset=preset,
        user_id=user_id,
        entity_ids=entity_ids,
    )


# ---------------------------------------------------------------------------
# TDF → metrics-prompt summariser
# ---------------------------------------------------------------------------


def summarize_tdf_for_metrics(tdf: dict[str, Any]) -> str:
    """Build a compact, model-readable summary of a TDF payload.

    The metrics agent doesn't need the full 1MB+ TDF — it needs the parts
    that ground its fit assessment: setting, atmosphere, tension level,
    plot summary, stakes, and any explicit historical/contextual notes.

    Args:
        tdf: TDF payload as produced by
            :meth:`GenerationPipeline.state_to_timepoint`.

    Returns:
        A short multiline string ready to drop into the metrics prompt.
    """
    parts: list[str] = []

    scene = tdf.get("scene_data") or {}
    if scene:
        setting = scene.get("setting") or ""
        atmosphere = scene.get("atmosphere") or ""
        tension = scene.get("tension_level") or ""
        focal = scene.get("focal_point") or ""
        if setting:
            parts.append(f"Setting: {setting}")
        if atmosphere:
            parts.append(f"Atmosphere: {atmosphere}")
        if tension:
            parts.append(f"Scene tension: {tension}")
        if focal:
            parts.append(f"Focal point: {focal}")

    moment = tdf.get("moment_data") or {}
    if moment:
        plot = moment.get("plot_summary") or ""
        stakes = moment.get("stakes") or ""
        arc = moment.get("tension_arc") or ""
        question = moment.get("central_question") or ""
        if plot:
            parts.append(f"Plot beat: {plot}")
        if stakes:
            parts.append(f"Stakes: {stakes}")
        if arc:
            parts.append(f"Tension arc: {arc}")
        if question:
            parts.append(f"Central question: {question}")

    char = tdf.get("character_data") or {}
    chars = char.get("characters") or []
    if chars:
        names = [c.get("name") for c in chars if c.get("name")]
        if names:
            parts.append("Characters present: " + ", ".join(names[:6]))

    grounding = tdf.get("grounding_data") or {}
    grounded_facts = grounding.get("facts") or grounding.get("verified_facts") or []
    if isinstance(grounded_facts, list) and grounded_facts:
        # Keep it short — only the first 3 facts.
        snippets = []
        for f in grounded_facts[:3]:
            if isinstance(f, str):
                snippets.append(f)
            elif isinstance(f, dict):
                snippets.append(f.get("statement") or f.get("text") or json.dumps(f))
        if snippets:
            parts.append("Grounded facts: " + "; ".join(snippets))

    if not parts:
        return tdf.get("query", "") or "(scene pipeline returned no usable summary)"

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Per-opportunity simulation
# ---------------------------------------------------------------------------


async def _simulate_one(
    *,
    index: int,
    goal: str,
    opportunity: OpportunityIn,
    preset: QualityPreset | None,
    generate_image: bool,
    user_id: str | None,
) -> dict[str, Any]:
    """Run scene pipeline + metrics agent for a single opportunity.

    Returns a dict ready to fold into a :class:`QuickSimTdfEntry`:
    ``{"success": bool, "tdf": dict | None, "quick_sim": QuickSimMetrics | None,
       "error": str | None, "latency_ms": int}``.

    Failures (pipeline or metrics) are caught and returned as
    ``success=False`` — the caller decides whether to refund credits and
    how to surface the failure in the batch response.
    """
    t0 = time.perf_counter()
    opp_dict = opportunity.model_dump()

    # Lazy import — avoids pulling app.prompts at module import time, which
    # would force the test conftest to set every env var early.
    from app.prompts.quick_sim import build_future_moment_query

    query = build_future_moment_query(goal=goal, opportunity=opp_dict)
    logger.info(
        "quick_sim: opportunity %d title=%r query=%r",
        index,
        opp_dict.get("title"),
        query[:120],
    )

    try:
        pipeline = _build_generation_pipeline(preset=preset, user_id=user_id)
        state = await asyncio.wait_for(
            pipeline.run(query, generate_image=generate_image),
            timeout=_PER_OPPORTUNITY_TIMEOUT_S,
        )

        timepoint = pipeline.state_to_timepoint(state)
        tdf = dict(timepoint.tdf_payload or {})
        tdf["status"] = timepoint.status.value if timepoint.status else "unknown"
        tdf["timepoint_id"] = timepoint.id
        tdf["slug"] = timepoint.slug

        scene_context = summarize_tdf_for_metrics(tdf)

        metrics_agent = QuickSimMetricsAgent(router=pipeline.router)
        metrics_result = await metrics_agent.run(
            QuickSimMetricsInput(
                goal=goal,
                opportunity=opp_dict,
                scene_context=scene_context,
            )
        )
        if not metrics_result.success or metrics_result.content is None:
            return {
                "success": False,
                "tdf": tdf,
                "quick_sim": None,
                "error": f"quick_sim metrics agent failed: {metrics_result.error}",
                "latency_ms": int((time.perf_counter() - t0) * 1000),
            }

        return {
            "success": True,
            "tdf": tdf,
            "quick_sim": metrics_result.content,
            "error": None,
            "latency_ms": int((time.perf_counter() - t0) * 1000),
        }

    except TimeoutError:
        return {
            "success": False,
            "tdf": None,
            "quick_sim": None,
            "error": f"quick_sim timed out after {_PER_OPPORTUNITY_TIMEOUT_S}s",
            "latency_ms": int((time.perf_counter() - t0) * 1000),
        }
    except Exception as exc:  # noqa: BLE001 — broad catch: one bad opportunity must not sink the batch
        logger.exception("quick_sim opportunity %d failed", index)
        return {
            "success": False,
            "tdf": None,
            "quick_sim": None,
            "error": f"{type(exc).__name__}: {exc}",
            "latency_ms": int((time.perf_counter() - t0) * 1000),
        }


# ---------------------------------------------------------------------------
# Result → response-entry builder
# ---------------------------------------------------------------------------


def _build_tdf_entry(
    *,
    index: int,
    opportunity: OpportunityIn,
    result: dict[str, Any],
) -> QuickSimTdfEntry:
    """Fold a :func:`_simulate_one` result into a :class:`QuickSimTdfEntry`.

    Pure function (no I/O) — the flat ``tdf_ref`` / ``opportunity_index`` /
    ``title`` / ``url`` / ``summary`` / ``probability`` / ``fit_score`` /
    ``effort_score`` / ``amount_usd`` / ``source`` shape is what the
    web-app's Find Money pipeline pairs against
    (``_seed_quick_sim_tdfs``), so real Flash output and the web-app
    seed fallback are interchangeable to the selection page.

    Args:
        index: Zero-based opportunity index (request order).
        opportunity: The original opportunity stub.
        result: A :func:`_simulate_one` result dict.

    Returns:
        A :class:`QuickSimTdfEntry` — one entry for this opportunity.
    """
    success = bool(result.get("success"))
    metrics = result.get("quick_sim")  # QuickSimMetrics | None

    return QuickSimTdfEntry(
        tdf_ref=f"flash:quick:{index}",
        opportunity_index=index,
        title=opportunity.title,
        url=opportunity.source_url,
        summary=opportunity.summary,
        probability=metrics.probability_of_award if metrics is not None else None,
        fit_score=metrics.fit_score if metrics is not None else None,
        effort_score=metrics.effort_score if metrics is not None else None,
        amount_usd=opportunity.amount,
        source="flash-quick-sim" if success else "flash-quick-sim-error",
        tdf=result.get("tdf"),
        quick_sim=metrics,
        error=result.get("error"),
        latency_ms=int(result.get("latency_ms", 0) or 0),
    )


# ---------------------------------------------------------------------------
# Billing — per-opportunity, gateway-aware
# ---------------------------------------------------------------------------


async def _maybe_spend_credits(
    *,
    session: AsyncSession,
    user: User | None,
    gateway_metered: bool,
    cost: int,
    description: str,
) -> bool:
    """Deduct credits for one opportunity, respecting the gateway header.

    Returns ``True`` if credits were spent (or skipped intentionally),
    ``False`` if the user lacked balance (caller should mark the
    opportunity as an error and not simulate it).

    The Gateway sets ``X-Gateway-Metered: true`` when it has already
    metered the request; in that case we MUST NOT double-charge. See the
    Flash Phase 1.0 Gateway Endpoints Spec (doc el-369y).
    """
    if user is None:
        return True  # AUTH_ENABLED=false or anonymous — no billing
    if gateway_metered:
        return True

    try:
        await spend_credits(
            session,
            user.id,
            cost,
            TransactionType.GENERATION,
            description=description,
        )
        await session.commit()
        return True
    except ValueError as e:
        # Insufficient balance or no account
        logger.info("quick_sim spend skipped for user=%s: %s", user.id, e)
        return False


async def _refund_credits(
    *,
    session: AsyncSession,
    user: User | None,
    gateway_metered: bool,
    cost: int,
    description: str,
) -> None:
    """Refund credits for a failed opportunity. Best-effort, never raises."""
    if user is None or gateway_metered:
        return
    try:
        await grant_credits(
            session,
            user.id,
            cost,
            TransactionType.REFUND,
            description=description,
        )
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("quick_sim refund failed for user=%s: %s", user.id, exc)


# ---------------------------------------------------------------------------
# Batch runner
# ---------------------------------------------------------------------------


async def _run_batch(
    *,
    request: QuickSimBatchRequest,
    user: User | None,
    session: AsyncSession,
    gateway_metered: bool,
) -> QuickSimBatchResponse:
    """Run a Quick-Sim batch and return the full JSON response.

    Each opportunity is billed before it runs (per-opportunity, unless
    the Gateway already metered the batch) and refunded if it fails.
    Up to :data:`_BATCH_CONCURRENCY` opportunities run at once; the
    response lists one :class:`QuickSimTdfEntry` per opportunity,
    ordered by request index, so it always pairs 1:1 with the request.
    """
    preset: QualityPreset | None = None
    if request.preset:
        try:
            preset = QualityPreset(request.preset.lower())
        except ValueError:
            logger.warning("quick_sim: invalid preset %r, defaulting", request.preset)
            preset = None

    cost = CREDIT_COSTS.get("quick_sim_per_opportunity", _DEFAULT_QUICK_SIM_COST)
    user_id = user.id if user is not None else None

    semaphore = asyncio.Semaphore(_BATCH_CONCURRENCY)

    async def _run(
        index: int, opportunity: OpportunityIn
    ) -> tuple[int, OpportunityIn, dict[str, Any], bool]:
        async with semaphore:
            opp_dict = opportunity.model_dump()
            # Bill BEFORE running — refund on failure. Matches /timepoints/generate.
            spent = await _maybe_spend_credits(
                session=session,
                user=user,
                gateway_metered=gateway_metered,
                cost=cost,
                description=f"quick-sim: {opp_dict.get('title', '')[:60]}",
            )
            if not spent:
                return (
                    index,
                    opportunity,
                    {
                        "success": False,
                        "tdf": None,
                        "quick_sim": None,
                        "error": (
                            f"Insufficient credits: quick-sim costs {cost} credits per opportunity."
                        ),
                        "latency_ms": 0,
                    },
                    False,  # billed=False so we don't refund a non-charge
                )
            result = await _simulate_one(
                index=index,
                goal=request.goal,
                opportunity=opportunity,
                preset=preset,
                generate_image=request.generate_image,
                user_id=user_id,
            )
            return index, opportunity, result, True

    tasks = [asyncio.create_task(_run(i, opp)) for i, opp in enumerate(request.opportunities)]
    settled = await asyncio.gather(*tasks)

    entries: list[QuickSimTdfEntry] = []
    completed = 0
    errored = 0

    for index, opportunity, result, billed in settled:
        if result.get("success"):
            completed += 1
        else:
            errored += 1
            # Refund — caller paid for an opportunity we couldn't complete.
            if billed:
                opp_title = (opportunity.title or "")[:60]
                await _refund_credits(
                    session=session,
                    user=user,
                    gateway_metered=gateway_metered,
                    cost=cost,
                    description=f"quick-sim refund (failed): {opp_title}",
                )
        entries.append(_build_tdf_entry(index=index, opportunity=opportunity, result=result))

    entries.sort(key=lambda e: e.opportunity_index)

    return QuickSimBatchResponse(
        tdfs=entries,
        completed=completed,
        errored=errored,
        total=len(request.opportunities),
        request_context=request.request_context,
    )


# ---------------------------------------------------------------------------
# Public endpoint
# ---------------------------------------------------------------------------


_GATEWAY_METERED_HEADER = "X-Gateway-Metered"


@router.post("/quick-sim-batch")
async def quick_sim_batch(
    body: QuickSimBatchRequest,
    request: Request,
    user: User | None = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> QuickSimBatchResponse:
    """Return future-moment TDFs + quick-sim metrics for a batch of opportunities.

    For each opportunity (1–15) provided, this:

    1. Wraps the opportunity in a future-tense framing query.
    2. Runs the standard 14-agent ``GenerationPipeline`` to produce a
       future-moment TDF.
    3. Runs a single :class:`QuickSimMetricsAgent` LLM call to extract
       ``probability_of_award``, ``fit_score``, ``effort_score``,
       ``effort_estimate``, ``key_risks``, and ``key_levers``.
    4. Folds the result into a :class:`QuickSimTdfEntry`.

    Response:
        A single ``application/json`` :class:`QuickSimBatchResponse`
        (HTTP 200) — **not** an SSE stream. The consumer is the
        web-app's ``run_quick_sim`` background job, and the API gateway
        cannot proxy ``text/event-stream``. ``tdfs`` carries one entry
        per opportunity (including failures, flagged
        ``source="flash-quick-sim-error"``) so the list pairs 1:1 with
        the request.

    Billing:
        Per-opportunity, using the ``quick_sim_per_opportunity`` cost
        from :data:`CREDIT_COSTS`. Failed opportunities are refunded.
        The Gateway header ``X-Gateway-Metered: true`` short-circuits
        all per-opportunity charges so the Gateway can meter at the
        batch level instead.

    Args:
        body: :class:`QuickSimBatchRequest`.
        request: Raw FastAPI request (used for the gateway-metered header).
        user: Authenticated user (or None when AUTH_ENABLED=false).
        session: DB session for credit ledger writes.

    Returns:
        :class:`QuickSimBatchResponse` serialised as JSON with HTTP 200.
    """
    gateway_metered = request.headers.get(_GATEWAY_METERED_HEADER, "").lower() == "true"

    logger.info(
        "quick_sim_batch: goal=%r count=%d user=%s gateway_metered=%s preset=%s",
        body.goal[:80],
        len(body.opportunities),
        user.id if user else None,
        gateway_metered,
        body.preset,
    )

    response = await _run_batch(
        request=body,
        user=user,
        session=session,
        gateway_metered=gateway_metered,
    )

    logger.info(
        "quick_sim_batch: done completed=%d errored=%d total=%d",
        response.completed,
        response.errored,
        response.total,
    )
    return response
