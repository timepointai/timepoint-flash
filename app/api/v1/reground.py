"""Internal entity re-grounding API.

Internal endpoints called by the Gateway on behalf of authenticated users.
All routes require X-Service-Key authentication.

Endpoints:
    POST /internal/entities/{entity_id}/reground - Trigger background re-grounding
    GET  /internal/entities/{entity_id}/reground/{task_id} - Poll task status

Examples:
    >>> # Trigger re-grounding
    >>> POST /internal/entities/fig_abc123/reground
    >>> X-Service-Key: <FLASH_SERVICE_KEY>
    >>> {}
    >>>
    >>> # Response
    >>> {"task_id": "rg_abc123", "status": "queued", "entity_id": "fig_abc123"}

Tests:
    - tests/unit/test_api_entities.py
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth.dependencies import require_service_key
from app.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal/entities", tags=["internal-entities"])

# In-memory task registry — maps task_id -> TaskRecord dict.
# Sufficient for polling within a single process lifetime; tasks are
# short-lived background jobs.
_tasks: dict[str, dict[str, Any]] = {}

# Grounding model for web search via OpenRouter
_GROUNDING_MODEL = "perplexity/sonar"
# Timeout for Clockchain + OpenRouter calls
_HTTP_TIMEOUT = httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)


# ── Request / Response models ─────────────────────────────────────────────────


class RegroundRequest(BaseModel):
    """Optional parameters for re-grounding."""

    deep: bool = False
    """If True, use Grok/X-search for enhanced grounding (costs 2 credits)."""

    x_handle: str | None = None
    """X/Twitter handle to search for additional entity signals."""


class RegroundResponse(BaseModel):
    task_id: str
    status: str
    entity_id: str


class TaskStatusResponse(BaseModel):
    task_id: str
    entity_id: str
    status: str
    """queued | running | completed | failed"""
    error: str | None = None
    grounding_model: str | None = None
    grounded_at: str | None = None
    confidence: float | None = None


# ── Background grounding task ─────────────────────────────────────────────────


async def _run_reground(
    task_id: str, entity_id: str, deep: bool, x_handle: str | None, user_id: str | None = None,
) -> None:
    """Background coroutine that grounds an entity and patches Clockchain."""
    settings = get_settings()
    record = _tasks[task_id]
    record["status"] = "running"

    try:
        # 1. Fetch figure data from Clockchain to get the display name
        clockchain_base = (settings.CLOCKCHAIN_ENTITY_URL or settings.CLOCKCHAIN_URL or "").rstrip(
            "/"
        )
        if not clockchain_base:
            raise RuntimeError("CLOCKCHAIN_URL not configured")

        cc_headers: dict[str, str] = {"Content-Type": "application/json"}
        if settings.CLOCKCHAIN_SERVICE_KEY:
            cc_headers["X-Service-Key"] = settings.CLOCKCHAIN_SERVICE_KEY
        if user_id:
            cc_headers["X-User-ID"] = user_id

        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            fig_resp = await client.get(
                f"{clockchain_base}/api/v1/figures/{entity_id.lstrip('/')}",
                headers=cc_headers,
            )

        if fig_resp.status_code == 404:
            raise ValueError(f"Figure not found: {entity_id}")
        fig_resp.raise_for_status()
        figure = fig_resp.json()
        display_name: str = figure.get("display_name", entity_id)

        # 2. Mark figure as "grounding" in Clockchain (optimistic status update)
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            await client.patch(
                f"{clockchain_base}/api/v1/figures/{entity_id.lstrip('/')}/ground",
                json={"grounding_status": "grounding"},
                headers=cc_headers,
            )

        # 3. Call OpenRouter with web-search plugin to ground the entity
        openrouter_key = settings.OPENROUTER_API_KEY
        if not openrouter_key:
            raise RuntimeError("OPENROUTER_API_KEY not configured — cannot ground entity")

        grounding_model = _GROUNDING_MODEL
        system_prompt = (
            "You are an entity grounding specialist. "
            "Research the given person or organization using web search. "
            "Return a JSON object with these fields: "
            "biography_summary (string), appearance_description (string), "
            "known_affiliations (list of strings), recent_activity_summary (string), "
            "confidence (float 0.0-1.0). "
            "Base ALL information strictly on the search results. "
            "If information is unavailable, use null."
        )
        user_prompt = (
            f"Ground this entity: {display_name}\n"
            f"Entity ID: {entity_id}\n"
            "Use web search to find current, accurate information about this person or organization."
        )

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        plugins: list[dict[str, Any]] = [{"id": "web", "max_results": 5}]

        # Deep mode: also search X/Twitter via Grok
        if deep and x_handle:
            grounding_model = "x-ai/grok-3-fast"
            messages.append(
                {
                    "role": "user",
                    "content": f"Also search X/Twitter for @{x_handle} for recent posts and activity.",
                }
            )

        payload: dict[str, Any] = {
            "model": grounding_model,
            "messages": messages,
            "plugins": plugins,
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
            "max_tokens": 1024,
        }

        async with httpx.AsyncClient(timeout=httpx.Timeout(connect=5.0, read=60.0, write=10.0, pool=5.0)) as client:
            or_resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {openrouter_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://timepointai.com",
                    "X-Title": "Timepoint Flash",
                },
                json=payload,
            )
        or_resp.raise_for_status()
        or_data = or_resp.json()

        # Parse response content
        content_str: str = or_data["choices"][0]["message"]["content"] or "{}"
        import json as _json

        try:
            grounding_result = _json.loads(content_str)
        except (_json.JSONDecodeError, KeyError):
            grounding_result = {}

        confidence = float(grounding_result.get("confidence", 0.5))
        grounded_at = datetime.now(timezone.utc)

        # Extract citation URLs from annotations
        annotations: list[dict] = or_data["choices"][0]["message"].get("annotations") or []
        source_urls = [
            a["url_citation"]["url"]
            for a in annotations
            if a.get("type") == "url_citation" and "url_citation" in a
        ]

        # 4. Patch Clockchain figure with grounding results
        patch_body: dict[str, Any] = {
            "grounding_status": "grounded",
            "grounded_at": grounded_at.isoformat(),
            "grounding_model": grounding_model,
            "grounding_confidence": confidence,
        }
        if source_urls:
            patch_body["grounding_sources"] = source_urls

        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            patch_resp = await client.patch(
                f"{clockchain_base}/api/v1/figures/{entity_id.lstrip('/')}/ground",
                json=patch_body,
                headers=cc_headers,
            )
        patch_resp.raise_for_status()

        # 5. Update task record
        record.update(
            {
                "status": "completed",
                "grounding_model": grounding_model,
                "grounded_at": grounded_at.isoformat(),
                "confidence": confidence,
            }
        )
        logger.info(
            "Entity re-grounding completed: %s (model=%s confidence=%.2f)",
            entity_id,
            grounding_model,
            confidence,
        )

    except Exception as exc:
        error_msg = str(exc)
        logger.warning("Entity re-grounding failed for %s: %s", entity_id, error_msg)
        record["status"] = "failed"
        record["error"] = error_msg

        # Mark figure as failed in Clockchain (best-effort)
        try:
            settings = get_settings()
            clockchain_base = (
                settings.CLOCKCHAIN_ENTITY_URL or settings.CLOCKCHAIN_URL or ""
            ).rstrip("/")
            cc_headers = {"Content-Type": "application/json"}
            if settings.CLOCKCHAIN_SERVICE_KEY:
                cc_headers["X-Service-Key"] = settings.CLOCKCHAIN_SERVICE_KEY
            async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
                await client.patch(
                    f"{clockchain_base}/api/v1/figures/{entity_id.lstrip('/')}/ground",
                    json={"grounding_status": "failed"},
                    headers=cc_headers,
                )
        except Exception:
            pass


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/{entity_id}/reground", response_model=RegroundResponse, status_code=202)
async def reground_entity(
    entity_id: str,
    request: Request,
    body: RegroundRequest = RegroundRequest(),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    _key: None = Depends(require_service_key),
) -> RegroundResponse:
    """Trigger background re-grounding for a Clockchain entity figure.

    Starts an async background task that:
    1. Fetches the figure from Clockchain
    2. Runs OpenRouter web-search grounding
    3. Patches Clockchain figure with grounding results

    Returns immediately with a task_id for status polling.

    Args:
        entity_id: Clockchain figure ID (may include leading slash).
        request: FastAPI request (used to extract X-User-ID header).
        body: Optional parameters — deep mode, X handle.

    Returns:
        202 Accepted with task_id.
    """
    task_id = f"rg_{uuid.uuid4().hex[:12]}"
    _tasks[task_id] = {
        "task_id": task_id,
        "entity_id": entity_id,
        "status": "queued",
        "error": None,
        "grounding_model": None,
        "grounded_at": None,
        "confidence": None,
    }

    # Extract user_id from forwarded header for Clockchain visibility
    user_id = request.headers.get("X-User-Id") or request.headers.get("X-User-ID")

    background_tasks.add_task(
        _run_reground,
        task_id=task_id,
        entity_id=entity_id,
        deep=body.deep,
        x_handle=body.x_handle,
        user_id=user_id,
    )
    logger.info("Entity re-grounding queued: entity=%s task=%s deep=%s", entity_id, task_id, body.deep)
    return RegroundResponse(task_id=task_id, status="queued", entity_id=entity_id)


@router.get("/{entity_id}/reground/{task_id}", response_model=TaskStatusResponse)
async def get_reground_status(
    entity_id: str,
    task_id: str,
    _key: None = Depends(require_service_key),
) -> TaskStatusResponse:
    """Poll the status of a re-grounding background task.

    Args:
        entity_id: Clockchain figure ID.
        task_id: Task ID returned by POST /reground.

    Returns:
        Task status: queued | running | completed | failed.
    """
    record = _tasks.get(task_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    if record.get("entity_id") != entity_id:
        raise HTTPException(status_code=404, detail="Task does not match entity_id")

    return TaskStatusResponse(
        task_id=task_id,
        entity_id=entity_id,
        status=record["status"],
        error=record.get("error"),
        grounding_model=record.get("grounding_model"),
        grounded_at=record.get("grounded_at"),
        confidence=record.get("confidence"),
    )
