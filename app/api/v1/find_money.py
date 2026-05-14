"""Find Money API endpoints.

Hosts the ``/api/v1/find-money/quick-sim-batch`` endpoint, which renders
1–15 opportunity stubs as future-moment TDFs and streams them back via
Server-Sent Events. The endpoint is consumed by the web app's Find Money
selection page (user picks top 5 of 15 before triggering Pro deep-sim).

This module deliberately reuses the existing 14-agent
:class:`app.core.pipeline.GenerationPipeline` for scene generation —
the only new model call is the small :class:`QuickSimMetricsAgent` that
extracts the structured fit fields after each scene completes.

Endpoints:
    POST /api/v1/find-money/quick-sim-batch — SSE batch quick-sim

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
    >>> # → text/event-stream of opportunity_start / opportunity_complete /
    >>> # opportunity_error / done events.

Tests:
    - tests/unit/test_api_find_money.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
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
    QuickSimMetrics,
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

# Concurrency: process opportunities in small chunks so we stream early
# results to the client while staying inside provider rate limits. The
# underlying pipeline already manages internal parallelism via its own
# semaphore; we only need to bound how many pipelines run at once.
_BATCH_CONCURRENCY = 3


# ---------------------------------------------------------------------------
# SSE event model (kept distinct from /timepoints StreamEvent so neither
# endpoint silently inherits the other's field changes).
# ---------------------------------------------------------------------------


class QuickSimEvent(BaseModel):
    """Server-Sent Event for /find-money/quick-sim-batch.

    Attributes:
        event: One of ``start``, ``opportunity_start``,
            ``opportunity_complete``, ``opportunity_error``, ``done``,
            ``error``.
        index: Zero-based opportunity index (None on batch-level events).
        opportunity: The original opportunity stub from the request.
        tdf: Full TDF payload from the scene pipeline (only on
            ``opportunity_complete``).
        quick_sim: :class:`QuickSimMetrics` for this opportunity (only on
            ``opportunity_complete``).
        error: Error message (only on ``opportunity_error`` / ``error``).
        data: Free-form batch-level metadata (count, latency, etc.).
        request_context: Opaque context echoed from the request.
    """

    event: str
    index: int | None = None
    opportunity: dict[str, Any] | None = None
    tdf: dict[str, Any] | None = None
    quick_sim: QuickSimMetrics | None = None
    error: str | None = None
    data: dict[str, Any] | None = None
    request_context: dict[str, Any] | None = None


def _format_sse(event: QuickSimEvent) -> str:
    """Format a QuickSimEvent as an SSE ``data:`` line.

    Args:
        event: The event to serialise.

    Returns:
        ``"data: <json>\\n\\n"``.
    """
    return f"data: {event.model_dump_json()}\n\n"


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

    Returns a dict ready to attach to a QuickSimEvent:
    ``{"success": bool, "tdf": dict | None, "quick_sim": QuickSimMetrics | None,
       "error": str | None, "latency_ms": int}``.

    Failures (pipeline or metrics) are caught and returned as
    ``success=False`` — the caller decides whether to surface as a
    per-opportunity error event or abort the batch.
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
        pipeline = GenerationPipeline(
            preset=preset,
            user_id=user_id,
        )
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
    except Exception as exc:  # noqa: BLE001 — broad catch on purpose: SSE must never raise
        logger.exception("quick_sim opportunity %d failed", index)
        return {
            "success": False,
            "tdf": None,
            "quick_sim": None,
            "error": f"{type(exc).__name__}: {exc}",
            "latency_ms": int((time.perf_counter() - t0) * 1000),
        }


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
    ``False`` if the user lacked balance (caller should emit error event).

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
# SSE streaming generator
# ---------------------------------------------------------------------------


async def _stream_batch(
    *,
    request: QuickSimBatchRequest,
    user: User | None,
    session: AsyncSession,
    gateway_metered: bool,
    disconnect_check,
) -> AsyncGenerator[str, None]:
    """Yield SSE events for a Quick-Sim batch.

    Streams ``opportunity_complete`` / ``opportunity_error`` events as
    each opportunity finishes (bounded concurrency), so the web app can
    progressively render cards instead of waiting for the full batch.
    """
    preset = None
    if request.preset:
        try:
            preset = QualityPreset(request.preset.lower())
        except ValueError:
            logger.warning("quick_sim: invalid preset %r, defaulting", request.preset)
            preset = None

    cost = CREDIT_COSTS.get("quick_sim_per_opportunity", _DEFAULT_QUICK_SIM_COST)
    user_id = user.id if user is not None else None

    # ---- start event -----------------------------------------------------
    yield _format_sse(
        QuickSimEvent(
            event="start",
            data={
                "goal": request.goal,
                "count": len(request.opportunities),
                "preset": preset.value if preset else (request.preset or "hyper"),
                "generate_image": request.generate_image,
                "concurrency": _BATCH_CONCURRENCY,
                "per_opportunity_cost": cost if not gateway_metered else 0,
            },
            request_context=request.request_context,
        )
    )

    # ---- run each opportunity --------------------------------------------
    semaphore = asyncio.Semaphore(_BATCH_CONCURRENCY)
    completed = 0
    errored = 0

    async def _run(index: int, opportunity: OpportunityIn) -> tuple[int, OpportunityIn, dict[str, Any], bool]:
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

    tasks = [
        asyncio.create_task(_run(i, opp))
        for i, opp in enumerate(request.opportunities)
    ]

    try:
        for finished in asyncio.as_completed(tasks):
            # If the client hung up, abort outstanding work.
            if disconnect_check is not None:
                try:
                    if await disconnect_check():
                        logger.info("quick_sim: client disconnected, aborting batch")
                        for t in tasks:
                            t.cancel()
                        return
                except Exception:
                    pass

            try:
                index, opportunity, result, billed = await finished
            except asyncio.CancelledError:
                continue
            except Exception as exc:  # noqa: BLE001
                logger.exception("quick_sim: task crashed")
                yield _format_sse(
                    QuickSimEvent(
                        event="opportunity_error",
                        error=f"task crashed: {type(exc).__name__}: {exc}",
                        request_context=request.request_context,
                    )
                )
                errored += 1
                continue

            opp_dict = opportunity.model_dump()

            if result["success"]:
                completed += 1
                yield _format_sse(
                    QuickSimEvent(
                        event="opportunity_complete",
                        index=index,
                        opportunity=opp_dict,
                        tdf=result["tdf"],
                        quick_sim=result["quick_sim"],
                        data={"latency_ms": result["latency_ms"]},
                        request_context=request.request_context,
                    )
                )
            else:
                errored += 1
                # Refund — caller paid for an opportunity we couldn't complete.
                if billed:
                    await _refund_credits(
                        session=session,
                        user=user,
                        gateway_metered=gateway_metered,
                        cost=cost,
                        description=(
                            f"quick-sim refund (failed): {opp_dict.get('title', '')[:60]}"
                        ),
                    )
                yield _format_sse(
                    QuickSimEvent(
                        event="opportunity_error",
                        index=index,
                        opportunity=opp_dict,
                        tdf=result["tdf"],
                        error=result["error"],
                        data={"latency_ms": result["latency_ms"], "refunded": billed},
                        request_context=request.request_context,
                    )
                )

    finally:
        # Cancel any still-running tasks (defensive)
        for t in tasks:
            if not t.done():
                t.cancel()

    # ---- done event ------------------------------------------------------
    yield _format_sse(
        QuickSimEvent(
            event="done",
            data={
                "completed": completed,
                "errored": errored,
                "total": len(request.opportunities),
            },
            request_context=request.request_context,
        )
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
) -> StreamingResponse:
    """Stream future-moment TDFs + quick-sim metrics for a batch of opportunities.

    For each opportunity (1–15) provided, this:

    1. Wraps the opportunity in a future-tense framing query.
    2. Runs the standard 14-agent ``GenerationPipeline`` to produce a
       future-moment TDF.
    3. Runs a single :class:`QuickSimMetricsAgent` LLM call to extract
       ``probability_of_award``, ``fit_score``, ``effort_estimate``,
       ``key_risks``, and ``key_levers``.
    4. Streams an ``opportunity_complete`` (or ``opportunity_error``)
       SSE event as soon as that opportunity finishes — the web app can
       render selection cards progressively.

    Billing:
        Per-opportunity, using the ``quick_sim_per_opportunity`` cost
        from :data:`CREDIT_COSTS`. Failed opportunities are refunded.
        The Gateway header ``X-Gateway-Metered: true`` short-circuits
        all per-opportunity charges so the Gateway can meter at the
        batch level instead.

    Response:
        ``text/event-stream`` of :class:`QuickSimEvent` events:
        ``start`` → ``opportunity_complete`` × N (interleaved with any
        ``opportunity_error`` events) → ``done``.

    Args:
        body: :class:`QuickSimBatchRequest`.
        request: Raw FastAPI request (used for disconnect detection and
            the gateway-metered header).
        user: Authenticated user (or None when AUTH_ENABLED=false).
        session: DB session for credit ledger writes.

    Returns:
        ``StreamingResponse`` with ``text/event-stream`` content type.
    """
    gateway_metered = (
        request.headers.get(_GATEWAY_METERED_HEADER, "").lower() == "true"
    )

    logger.info(
        "quick_sim_batch: goal=%r count=%d user=%s gateway_metered=%s preset=%s",
        body.goal[:80],
        len(body.opportunities),
        user.id if user else None,
        gateway_metered,
        body.preset,
    )

    return StreamingResponse(
        _stream_batch(
            request=body,
            user=user,
            session=session,
            gateway_metered=gateway_metered,
            disconnect_check=request.is_disconnected,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # disable nginx buffering
        },
    )
