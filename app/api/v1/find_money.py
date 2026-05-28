"""Find Money API endpoints.

Hosts the ``/api/v1/find-money/quick-sim-batch`` endpoint, which renders
1–15 opportunity stubs as future-moment TDFs and returns them as a
single JSON object. The endpoint is consumed by the web app's Find
Money pipeline (``run_quick_sim`` in
``timepoint-web-app/app/find_money/runs/jobs.py``) — a server-side
background job, not a browser, so there is no value in streaming, and
the API gateway cannot proxy ``text/event-stream`` responses.

This module reuses the existing :class:`app.core.pipeline.GenerationPipeline`,
but drives it through its LIGHT entry point
(:meth:`~app.core.pipeline.GenerationPipeline.run_quick_sim`) rather than
the full ~14-agent render. Quick-sim is a fast first-pass read, so the
pipeline is parameterized down to the five LLM calls that actually feed
the fit assessment — Judge -> Timeline -> Scene -> CharacterIdentification
-> Moment — skipping character bios, the relationship graph, dialog,
camera composition, and image generation. The only other model call is
the small :class:`QuickSimMetricsAgent` that extracts the structured fit
fields after each scene completes. Full scene/character/image detail is
the downstream Pro deep-sim's job, not quick-sim's.

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
from app.database import get_db_session, get_session
from app.models import TimepointVisibility
from app.models_auth import TransactionType, User
from app.schemas.quick_sim import (
    OpportunityIn,
    QuickSimBatchRequest,
    QuickSimBatchResponse,
    QuickSimTdfEntry,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/find-money", tags=["find-money"])


# Module-level set of in-flight background image-generation tasks. Keeping a
# reference here prevents the asyncio event loop from garbage-collecting the
# task before it completes — see ``app/mcp_server.py`` for the same pattern.
# A ``done_callback`` removes the task on completion so this never grows
# unbounded.
_BACKGROUND_IMG_TASKS: set[asyncio.Task[None]] = set()


# Per-opportunity credit cost. Keep this tiny — Find Money batches up to 15
# opportunities and a single batch must remain cheap enough that users will
# actually run the discovery step before paying for the slower Pro deep-sim.
# Authoritative cost table lives in app/auth/credits.py CREDIT_COSTS.
_DEFAULT_QUICK_SIM_COST = 2


# Hard wall-clock cap for a single opportunity (quick-sim pipeline +
# metrics agent). Quick-sim runs the LIGHT pipeline path
# (:meth:`GenerationPipeline.run_quick_sim` — five LLM calls, no
# bios/graph/dialog/camera/image), so a healthy opportunity finishes in
# a few seconds. This cap is a safety net for a genuinely hung provider
# call, not the expected path. The standard generate-stream uses 360s;
# the original quick-sim-batch used 120s while still running the full
# 14-agent render — both were far too generous once the pipeline is
# parameterized down to the quick-sim subset.
_PER_OPPORTUNITY_TIMEOUT_S = 60

# Concurrency: how many opportunity pipelines run at once. The quick-sim
# path is dramatically lighter than the full render (five mostly
# sequential LLM calls vs ~10-14, no parallel bio fan-out, no image
# generation), so it is safe to run more of them concurrently than the
# original value of 3. At concurrency 6 a full 15-opportunity batch is
# ~3 waves. Measured (task el-3pwch): a 6-opportunity wave is ~43s and a
# 12-opportunity batch ~98s — well inside the web-app's 180s httpx
# timeout. The residual gap to the 60s product target is the per-LLM-call
# latency floor documented in spec el-4myis, not a concurrency knob. The
# underlying pipeline still manages its own internal parallelism via its
# semaphore.
_BATCH_CONCURRENCY = 6


# Quick-sim Flash tuning — the "fast model + tight budget" half of the
# parameterization (``run_quick_sim`` is the "minimal agent subset" half).
#
# Quick-sim is latency-critical and runs in batches, so it pins the
# per-opportunity pipeline to the fastest *reliable* text path instead of
# trusting the request's ``preset``:
#
#   * Model: ``gemini-2.5-flash``, called Google-native. The ``hyper``
#     preset's ``google/gemini-2.0-flash-001`` routes through OpenRouter,
#     whose shared upstream account is chronically 429 rate-limited (see
#     ``project_openrouter_keys.md``) — every call eats a ~7s rate-limit
#     round-trip before falling back. Google-native ``gemini-2.5-flash``
#     answers a structured call in ~1-2s. ``gemini-2.5-flash`` is
#     ``VerifiedModels.GOOGLE_TEXT[0]``, so it always passes preset
#     validation.
#   * Thinking: capped to a small fixed budget (``thinking_level=512``).
#     ``gemini-2.5-flash`` defaults to a *dynamic* thinking budget; on a
#     JSON-schema structured call it burns 5-10s "thinking" for a
#     sub-1k-token answer. A small fixed budget keeps each call to ~1-3s
#     while still leaving the Judge agent enough reasoning room to
#     classify the future-moment framing query as valid (a hard ``0``
#     budget makes the Judge reject it). ``thinking_level`` is forwarded
#     to the Google provider as ``ThinkingConfig.thinking_budget``.
#   * Output cap: ``max_tokens`` kept generous-but-bounded; the quick-sim
#     agents emit small structured payloads (largest observed ~850
#     tokens), so 4096 is plenty of headroom without inviting runaway
#     generations.
#
# The ``preset`` the caller passes still flows through (it selects the
# parallelism mode), but the text model + thinking config below override
# it so quick-sim stays fast regardless of which preset the web-app sends.
_QUICK_SIM_TEXT_MODEL = "gemini-2.5-flash"
_QUICK_SIM_LLM_PARAMS: dict[str, Any] = {"thinking_level": 512, "max_tokens": 4096}


# ---------------------------------------------------------------------------
# GenerationPipeline construction seam
# ---------------------------------------------------------------------------


def _build_generation_pipeline(
    *,
    preset: QualityPreset | None,
    user_id: str | None,
    entity_ids: list[str] | None = None,
    text_model: str | None = None,
    llm_params: dict[str, Any] | None = None,
) -> GenerationPipeline:
    """Construct the GenerationPipeline with the kwargs Quick-Sim relies on.

    Quick-sim drives the returned pipeline through its LIGHT entry point,
    :meth:`GenerationPipeline.run_quick_sim` — not the full ~14-agent
    :meth:`GenerationPipeline.run` — and pins it to a fast, reliable text
    path via ``text_model`` + ``llm_params`` (see
    :data:`_QUICK_SIM_TEXT_MODEL` / :data:`_QUICK_SIM_LLM_PARAMS`).
    Construction otherwise mirrors the standard pipeline, so this seam
    still guards the ``__init__`` signature contract.

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
        text_model: Optional text-model override. Quick-sim passes
            :data:`_QUICK_SIM_TEXT_MODEL` so the per-opportunity pipeline
            uses the fast Google-native path rather than the request
            preset's (possibly rate-limited) model.
        llm_params: Optional per-call LLM params (e.g. ``thinking_level``,
            ``max_tokens``). Quick-sim passes :data:`_QUICK_SIM_LLM_PARAMS`
            to disable extended thinking and bound output.

    Returns:
        A ready-to-run :class:`GenerationPipeline`.
    """
    return GenerationPipeline(
        preset=preset,
        user_id=user_id,
        entity_ids=entity_ids,
        text_model=text_model,
        llm_params=llm_params,
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
# Per-opportunity persistence
# ---------------------------------------------------------------------------


async def _persist_quick_sim_timepoint(
    timepoint: Any,
    *,
    user_id: str | None,
) -> str | None:
    """Save a quick-sim future-moment Timepoint to Flash's DB.

    Quick-sim returns a generated UUID + slug to the web-app, which uses
    them to build a "Preview the moment" link at
    ``/timepoint/{slug}?id={timepoint_id}``. That link resolves via Flash's
    ``GET /api/v1/timepoints/{id}`` — which 404s unless we actually save
    the row here. (Diagnosed against run 31:
    ``5305ea61-b806-4046-979e-db1102ae6f93`` was never in the DB.)

    The row is owned by the requesting user and marked PRIVATE — these are
    per-run private simulations, not curated public timepoints. Visibility
    inheritance follows the same pattern as
    ``/timepoints/generate/sync`` (see :mod:`app.api.v1.timepoints`).

    Uses a fresh ``get_session()`` rather than the request-scoped session
    because the batch handler runs up to ``_BATCH_CONCURRENCY`` of these
    concurrently and the request session is also being used for credit
    ledger writes.

    On any DB error this returns ``None`` (and logs) so the quick-sim
    response still carries the in-memory ``tdf`` — the only loss is the
    Preview link, which the web-app suppresses when ``timepoint_id`` is
    absent.
    """
    try:
        if user_id is not None:
            timepoint.user_id = user_id
            # Quick-sim moments are per-user private simulations.
            timepoint.visibility = TimepointVisibility.PRIVATE
        else:
            # Anonymous quick-sim (AUTH_ENABLED=false) — nobody owns the row,
            # so PRIVATE would lock it out of GET /timepoints/{id} forever
            # (check_visibility_access 403s when there is no owner). Keep it
            # PUBLIC so the Preview link still resolves.
            timepoint.visibility = TimepointVisibility.PUBLIC

        async with get_session() as session:
            session.add(timepoint)
            await session.commit()
            await session.refresh(timepoint)
            return timepoint.id
    except Exception as exc:  # noqa: BLE001 — persistence is best-effort
        logger.warning(
            "quick_sim: failed to persist timepoint id=%s slug=%s user=%s: %s",
            getattr(timepoint, "id", None),
            getattr(timepoint, "slug", None),
            user_id,
            exc,
        )
        return None


# ---------------------------------------------------------------------------
# Async (fire-and-forget) image generation for a persisted quick-sim moment
# ---------------------------------------------------------------------------


async def _run_quick_sim_image_gen(
    *,
    timepoint_id: str,
    pipeline: GenerationPipeline,
    state: Any,
) -> None:
    """Generate + persist an image for an already-persisted quick-sim moment.

    Quick-sim's :meth:`GenerationPipeline.run_quick_sim` deliberately skips
    the image path (ImagePrompt -> ImagePromptOptimize -> ImageGeneration)
    to keep per-opportunity latency under the 60s product target. That
    leaves the persisted future-moment row with ``image_url=NULL``, so the
    web-app's "Preview the moment" page renders a placeholder.

    This helper fills that gap *after* the user has their fit/probability
    metrics. It is fire-and-forget — the quick-sim response returns first;
    the image fills in ~30s later on a subsequent page load.

    All failures are swallowed (logged at WARNING) per the contract:
    quick-sim already returned successfully, so a failed image must not
    crash anything. There is no retry — a missed image just stays as the
    placeholder, exactly as it would have without this helper.

    The function opens its **own** ``get_session()`` because the originating
    request's session is closed by the time this task runs (the response
    has already been returned). This mirrors the pattern in
    :func:`app.core.background_grounding.run_background_grounding`.

    Args:
        timepoint_id: Persisted Timepoint row to update on success.
        pipeline: The same ``GenerationPipeline`` instance that produced
            ``state`` — reused so its router config (and model selection)
            is identical to the run that produced the row.
        state: The completed quick-sim ``PipelineState``. Carries judge /
            timeline / scene / character / moment data — enough for the
            ImagePrompt agent to compose a prompt without re-running the
            text path.
    """
    try:
        # ImagePrompt is the cheap step; the meaningful cost is in
        # ImageGeneration. Run them sequentially on the existing state.
        state = await pipeline._step_image_prompt(state)
        if state.image_prompt_data is None:
            logger.warning(
                "quick_sim background image: image-prompt step produced no "
                "data for timepoint %s — skipping image generation",
                timepoint_id,
            )
            return

        # Optimize the prompt (best-effort; image gen still runs if this
        # fails — _step_image_generation falls back to the full prompt).
        state = await pipeline._step_image_prompt_optimize(state)

        # Image generation. The pipeline's normal model selection applies
        # (preset / get_image_fallback_model permissive fallback) — quick-sim
        # does NOT hardcode an image model here.
        state = await pipeline._step_image_generation(state)
        if not state.image_base64:
            logger.warning(
                "quick_sim background image: image generation returned no bytes for timepoint %s",
                timepoint_id,
            )
            return

        # Encode the bytes as a data URL exactly the way state_to_timepoint
        # does for the synchronous full-pipeline path, so quick-sim moments
        # and full moments store image_url in the same canonical shape.
        image_format = "jpeg"
        if state.image_base64.startswith("iVBOR"):
            image_format = "png"
        elif state.image_base64.startswith("R0lGOD"):
            image_format = "gif"
        image_url = f"data:image/{image_format};base64,{state.image_base64}"

        # Update the persisted row in a fresh session — the request's
        # session has long since closed.
        from sqlalchemy import select

        from app.models import Timepoint

        async with get_session() as session:
            result = await session.execute(select(Timepoint).where(Timepoint.id == timepoint_id))
            tp = result.scalar_one_or_none()
            if tp is None:
                logger.warning(
                    "quick_sim background image: timepoint %s not found — "
                    "row may have been deleted between persistence and image gen",
                    timepoint_id,
                )
                return
            tp.image_url = image_url
            tp.image_base64 = state.image_base64
            await session.commit()
            logger.info(
                "quick_sim background image: timepoint %s image_url populated",
                timepoint_id,
            )
    except Exception:  # noqa: BLE001 — best-effort; no retry, no crash
        logger.warning(
            "quick_sim background image: failed for timepoint %s",
            timepoint_id,
            exc_info=True,
        )


def _schedule_quick_sim_image_gen(
    *,
    timepoint_id: str,
    pipeline: GenerationPipeline,
    state: Any,
) -> asyncio.Task[None]:
    """Schedule :func:`_run_quick_sim_image_gen` as a fire-and-forget task.

    The task reference is held in the module-level ``_BACKGROUND_IMG_TASKS``
    set so the event loop does not garbage-collect it before completion;
    a done-callback removes it on completion. The caller does NOT await
    the returned task — quick-sim's response returns immediately.
    """
    task = asyncio.create_task(
        _run_quick_sim_image_gen(
            timepoint_id=timepoint_id,
            pipeline=pipeline,
            state=state,
        ),
        name=f"quick-sim-img-{timepoint_id}",
    )
    _BACKGROUND_IMG_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_IMG_TASKS.discard)
    return task


# ---------------------------------------------------------------------------
# Per-opportunity simulation
# ---------------------------------------------------------------------------


async def _simulate_one(
    *,
    index: int,
    goal: str,
    opportunity: OpportunityIn,
    preset: QualityPreset | None,
    user_id: str | None,
) -> dict[str, Any]:
    """Run the quick-sim pipeline + metrics agent for a single opportunity.

    Uses :meth:`GenerationPipeline.run_quick_sim` — the LIGHT pipeline
    path (Judge -> Timeline -> Scene -> CharacterIdentification ->
    Moment, five LLM calls) rather than the full ~14-agent
    :meth:`GenerationPipeline.run`. Quick-sim is a fast first-pass read:
    it needs scene + moment + character names to ground the metrics
    agent, and nothing else. Character bios, the relationship graph,
    dialog, camera composition, and image generation are all skipped —
    that detail (and the image) is the downstream Pro deep-sim's job.
    Because the light path never renders an image, the request's
    ``generate_image`` flag does not apply to quick-sim and is ignored.

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
        pipeline = _build_generation_pipeline(
            preset=preset,
            user_id=user_id,
            text_model=_QUICK_SIM_TEXT_MODEL,
            llm_params=dict(_QUICK_SIM_LLM_PARAMS),
        )
        # LIGHT path: run_quick_sim runs only Judge -> Timeline -> Scene ->
        # CharacterIdentification -> Moment (five LLM calls), not the full
        # ~14-agent render — and the pipeline is pinned to the fast
        # Google-native text path with the thinking budget capped. Together
        # these keep a single opportunity to a few seconds instead of >90s.
        state = await asyncio.wait_for(
            pipeline.run_quick_sim(query),
            timeout=_PER_OPPORTUNITY_TIMEOUT_S,
        )

        timepoint = pipeline.state_to_timepoint(state)
        # Persist the quick-sim future-moment so web-app's "Preview the moment"
        # link (which points at /timepoint/{slug}?id={timepoint_id}) can resolve
        # via GET /api/v1/timepoints/{id}. Without this row, every Preview
        # click 404s — see fix-quick-sim-persist-timepoints-2026-05-27.
        # Quick-sim moments are private to the requesting user (not user-curated
        # public timepoints), so visibility=PRIVATE. Persist failure must NOT
        # fail the quick-sim: log + clear timepoint_id so the web-app skips
        # rendering the Preview link.
        persisted_id = await _persist_quick_sim_timepoint(timepoint, user_id=user_id)

        # Fire-and-forget background image generation. Quick-sim's light path
        # deliberately skipped ImagePrompt + ImageGeneration to keep latency
        # under the 60s product target, which leaves the persisted row with
        # image_url=NULL and the web-app's Preview page rendering a
        # placeholder. Schedule the image gen AFTER successful persistence
        # (only on the success path — never fire when persistence failed,
        # because there is no row to update). The response returns
        # immediately; the image fills in ~30s later on the next page load.
        # Failures inside the task are logged but never crash quick-sim.
        if persisted_id is not None:
            _schedule_quick_sim_image_gen(
                timepoint_id=persisted_id,
                pipeline=pipeline,
                state=state,
            )

        tdf = dict(timepoint.tdf_payload or {})
        tdf["status"] = timepoint.status.value if timepoint.status else "unknown"
        tdf["timepoint_id"] = persisted_id  # None if persistence failed
        tdf["slug"] = timepoint.slug

        scene_context = summarize_tdf_for_metrics(tdf)

        # The metrics agent reuses the pipeline's router (same fast,
        # Google-native text path) AND the same capped thinking budget —
        # without _QUICK_SIM_LLM_PARAMS it would fall back to the model's
        # dynamic thinking budget and become the slowest step in the path.
        metrics_agent = QuickSimMetricsAgent(
            router=pipeline.router,
            llm_params=dict(_QUICK_SIM_LLM_PARAMS),
        )
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
    2. Runs the LIGHT pipeline path
       (:meth:`GenerationPipeline.run_quick_sim` — Judge -> Timeline ->
       Scene -> CharacterIdentification -> Moment, five LLM calls) to
       produce a future-moment TDF. Character bios, the relationship
       graph, dialog, camera, and image generation are skipped — that
       detail is the downstream Pro deep-sim's job, and running the full
       ~14-agent render here made a single opportunity take >90s.
    3. Runs a single :class:`QuickSimMetricsAgent` LLM call to extract
       ``probability_of_award``, ``fit_score``, ``effort_score``,
       ``effort_estimate``, ``key_risks``, and ``key_levers``.
    4. Folds the result into a :class:`QuickSimTdfEntry`.

    Up to :data:`_BATCH_CONCURRENCY` opportunities run concurrently. The
    light path took a single opportunity from >90s (the original timeout)
    down to ~30-40s; a full 15-opportunity batch settles well inside the
    web-app's 180s httpx timeout. The request's ``generate_image`` flag
    does not apply to the light path (quick-sim never renders an image)
    and is ignored.

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
