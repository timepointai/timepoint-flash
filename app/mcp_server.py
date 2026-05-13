"""MCP (Model Context Protocol) server for TIMEPOINT Flash.

Exposes Flash's timepoint-generation pipeline to MCP-compatible agents over
the Streamable HTTP transport.  Mounted from :mod:`app.main` at ``/mcp`` and
protected by :class:`app.middleware.bearer_auth.BearerAuthMiddleware`.

The server exposes exactly one tool — ``tp_flash_generate`` — matching the
spec in API-5:

    "stand up Flash MCP server at flash.timepointai.com/mcp/ exposing
     tp_flash_generate tool (Bearer auth)"

The tool is non-blocking: it creates a timepoint row in PROCESSING state,
schedules the pipeline as an asyncio background task, and returns the
timepoint id + a ready-to-curl status URL.  MCP clients poll
``GET https://flash.timepointai.com/api/v1/timepoints/{id}`` (same Bearer
token) for progress.  This matches the pattern Belle's memo describes —
MCP clients with short timeouts can't hold a connection open for a full
generation (30–60s), so the tool returns a reference instead.

Config snippet for MCP clients::

    mcp_servers:
      timepoint-flash:
        url: https://flash.timepointai.com/mcp/
        headers:
          Authorization: "Bearer ${TIMEPOINT_API_KEY}"
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from app.middleware.bearer_auth import get_current_bearer_user

logger = logging.getLogger("timepoint_flash.mcp")


# ---------------------------------------------------------------------------
# Server instance
# ---------------------------------------------------------------------------

# DNS rebinding protection is disabled because the MCP app is mounted as a
# sub-app behind FastAPI (which handles its own CORS) and Railway's reverse
# proxy validates hosts.  The default allowed_hosts list only includes
# localhost, which would reject production hosts like flash.timepointai.com.
_transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=False,
)

mcp = FastMCP(
    name="TimepointFlash",
    instructions=(
        "TIMEPOINT Flash — AI-powered temporal simulation. Use "
        "`tp_flash_generate` to start a timepoint generation from a "
        "natural-language query (e.g. 'signing of the declaration'). The "
        "tool returns an `id` and a `status_url`; poll "
        "GET https://flash.timepointai.com/api/v1/timepoints/{id} with the "
        "same Bearer token to check status and fetch the completed "
        "timepoint."
    ),
    host="0.0.0.0",
    stateless_http=True,
    streamable_http_path="/",
    transport_security=_transport_security,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_ALLOWED_PRESETS: frozenset[str] = frozenset({"hyper", "balanced", "hd"})
_ALLOWED_VISIBILITIES: frozenset[str] = frozenset({"public", "private"})
_ALLOWED_MODEL_POLICIES: frozenset[str] = frozenset({"permissive"})


def _current_user() -> str:
    """Return the Bearer-authenticated user_id for the current request.

    Falls back to a synthetic id if the middleware hasn't run — this should
    never happen in production (the middleware is always mounted in front of
    the MCP app) but keeps tests and local dev usable.
    """
    user = get_current_bearer_user()
    if user:
        return user
    return "mcp-anonymous"


def _validate_enum(
    value: str | None, allowed: frozenset[str], field: str
) -> tuple[str | None, str | None]:
    """Return ``(value, None)`` or ``(None, error_message)`` for an enum field.

    Accepts ``None``/empty as "not supplied" (returns ``(None, None)``).
    """
    if not value:
        return None, None
    normalized = value.strip().lower()
    if not normalized:
        return None, None
    if normalized not in allowed:
        return None, (f"Invalid {field}={value!r}. Expected one of: {sorted(allowed)}.")
    return normalized, None


# ---------------------------------------------------------------------------
# Gateway-aware user/credit helpers
# ---------------------------------------------------------------------------
#
# The MCP path goes DIRECTLY to flash.timepointai.com/mcp/ — it bypasses the
# Gateway's metering middleware that normally deducts credits for REST calls
# proxied through api.timepointai.com.  That means two things the REST path
# normally handles for us happen here instead:
#
# 1. **User provisioning.**  ``BearerAuthMiddleware`` resolves a ``tp_gw_*``
#    token to the *Gateway*'s ``user_id``.  That UUID is not guaranteed to
#    exist in Flash's local ``users`` table — and ``timepoints.user_id`` has
#    a FK to ``users.id``.  Setting ``timepoint.user_id`` to an unknown UUID
#    blows up with ``ForeignKeyViolationError`` and the tool returns
#    ``{"error": ...}`` instead of the documented ``{"id", "status", ...}``
#    shape.  We mirror ``/api/v1/users/resolve`` semantics: look up by id
#    first, then by ``external_id``, and auto-provision a Flash User row
#    when neither matches.
#
# 2. **Credit deduction.**  The Gateway is the authoritative credit ledger
#    (see ``project_auth_consolidation.md``).  REST callers get debited by
#    the metering middleware in front of the Gateway proxy; MCP callers
#    don't.  We deduct up-front via the Gateway's internal
#    ``/internal/credits/spend`` endpoint so the same ``tp_gw_*`` key
#    produces the same balance change regardless of transport.


_GATEWAY_GENERATION_COST: int = 5  # mirrors CREDIT_COSTS["generate_balanced"]


async def _resolve_or_provision_flash_user(user_id: str) -> str | None:
    """Return a Flash ``User.id`` for the gateway-resolved ``user_id``.

    Looks up by ``User.id`` first, then ``User.external_id`` (the gateway
    user_id is stored there by ``/api/v1/users/resolve``).  If neither
    matches, provisions a fresh Flash User + vestigial CreditAccount,
    matching the auto-provisioning behaviour of ``resolve_user`` in
    ``app/api/v1/users.py``.  Returns ``None`` on any error so the caller
    can fall back to creating an unowned timepoint rather than 500'ing.

    The Flash User's ``apple_sub`` placeholder uses a ``gateway:`` prefix
    so it can never collide with a real Apple Sign-In subject (those are
    opaque Apple identifiers, not UUID-shaped).  ``external_id`` is set to
    the gateway user_id so a subsequent ``/api/v1/users/resolve`` call for
    the same identity is idempotent.
    """
    from sqlalchemy import select
    from sqlalchemy.exc import IntegrityError

    from app.database import get_session
    from app.models_auth import CreditAccount, User

    try:
        async with get_session() as session:
            existing = await session.execute(select(User).where(User.id == user_id))
            user = existing.scalar_one_or_none()
            if user is None:
                existing = await session.execute(
                    select(User).where(User.external_id == user_id)
                )
                user = existing.scalar_one_or_none()
            if user is not None:
                return user.id

            new_user = User(
                id=str(uuid.uuid4()),
                apple_sub=f"gateway:{user_id}",
                external_id=user_id,
            )
            session.add(new_user)
            try:
                await session.flush()
                # Match resolve_user(): every Flash User gets a credit
                # account row.  The Gateway is the authoritative ledger, so
                # we seed balance=0 here instead of granting Flash signup
                # credits a second time.
                session.add(
                    CreditAccount(
                        id=str(uuid.uuid4()),
                        user_id=new_user.id,
                        balance=0,
                        lifetime_earned=0,
                    )
                )
                await session.commit()
                logger.info("Provisioned Flash user %s for gateway user_id=%s", new_user.id, user_id)
                return new_user.id
            except IntegrityError:
                # Race: a concurrent /resolve or /mcp call won.  Re-look up
                # by external_id and use whichever row landed.
                await session.rollback()
                existing = await session.execute(
                    select(User).where(User.external_id == user_id)
                )
                user = existing.scalar_one_or_none()
                return user.id if user is not None else None
    except Exception:
        logger.exception("Failed to resolve/provision Flash user for gateway id=%s", user_id)
        return None


async def _gateway_credit_op(
    path: str,
    payload: dict[str, Any],
) -> tuple[bool, dict[str, Any] | None]:
    """POST to a Gateway ``/internal/credits/*`` endpoint.

    Returns ``(ok, body)`` — ``ok`` is True only when the HTTP call returned
    2xx AND the JSON body has ``success: True``.  ``body`` is the parsed
    JSON when available so the caller can surface ``error`` strings or
    ``balance_after``.

    Both ``GATEWAY_INTERNAL_URL`` and ``GATEWAY_SERVICE_KEY`` must be set —
    when either is missing we return ``(True, None)`` so local dev (no
    Gateway) doesn't break the MCP tool.  This matches the soft-fail
    behaviour of ``BearerAuthMiddleware``.
    """
    gateway_url = os.environ.get("GATEWAY_INTERNAL_URL", "").rstrip("/")
    service_key = os.environ.get("GATEWAY_SERVICE_KEY", "")
    if not gateway_url or not service_key:
        return True, None

    url = f"{gateway_url}{path}"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                url,
                json=payload,
                headers={"X-Service-Key": service_key, "Content-Type": "application/json"},
            )
    except (httpx.HTTPError, OSError) as exc:
        logger.warning("Gateway %s failed (network): %s", path, exc)
        return False, None

    if response.status_code != 200:
        logger.warning("Gateway %s returned HTTP %d", path, response.status_code)
        return False, None

    try:
        body = response.json()
    except ValueError:
        logger.warning("Gateway %s returned non-JSON body", path)
        return False, None

    if not isinstance(body, dict):
        return False, None
    return bool(body.get("success", False)), body


async def _gateway_spend_credits(
    user_id: str, cost: int, description: str
) -> tuple[bool, str | None]:
    """Deduct ``cost`` credits from the Gateway's ledger for ``user_id``.

    Returns ``(success, error_message)``.  Success is True both when the
    Gateway confirms a deduction and when the Gateway is intentionally
    unconfigured (local dev).  On failure, ``error_message`` carries a
    short reason suitable for an MCP ``{"error": ...}`` response.
    """
    ok, body = await _gateway_credit_op(
        "/internal/credits/spend",
        {
            "user_id": user_id,
            "cost": cost,
            "transaction_type": "generation",
            "description": description,
        },
    )
    if ok:
        return True, None
    err = (body or {}).get("error") if isinstance(body, dict) else None
    return False, err or "Credit deduction failed (gateway unreachable or rejected)"


async def _gateway_refund_credits(user_id: str, amount: int, description: str) -> None:
    """Best-effort refund via the Gateway.  Logged on failure, never raises."""
    ok, body = await _gateway_credit_op(
        "/internal/credits/grant",
        {
            "user_id": user_id,
            "amount": amount,
            "transaction_type": "refund",
            "description": description,
        },
    )
    if not ok:
        err = (body or {}).get("error") if isinstance(body, dict) else None
        logger.critical(
            "Gateway credit refund FAILED: user=%s amount=%d error=%s",
            user_id,
            amount,
            err,
        )


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def tp_flash_generate(
    query: str,
    generate_image: bool = False,
    preset: str | None = None,
    text_model: str | None = None,
    image_model: str | None = None,
    visibility: str | None = None,
    model_policy: str | None = None,
    entity_ids: list[str] | None = None,
    request_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Start a TIMEPOINT Flash generation.

    Creates a timepoint row in ``processing`` state, kicks off the
    generation pipeline as an asyncio background task, and returns
    immediately with the timepoint id and a status URL.  Poll
    ``GET https://flash.timepointai.com/api/v1/timepoints/{id}`` with the
    same Bearer token to check status and fetch the finished timepoint.

    Args:
        query: Natural-language temporal query (3–500 chars), e.g.
            "signing of the declaration", "rome 50 BCE",
            "battle of thermopylae". **Required.**
        generate_image: Whether to generate an image alongside the text
            (adds ~30s).  Default False.
        preset: Quality preset — one of ``"hyper"`` (fastest),
            ``"balanced"`` (default), ``"hd"`` (best quality).  Omit to use
            the server default.
        text_model: Optional custom text-model override
            (e.g. ``"google/gemini-2.0-flash-001"``).  Overrides preset.
        image_model: Optional custom image-model override (OpenRouter
            ``org/model`` format or Google native id).
        visibility: ``"public"`` (default) or ``"private"``.  Private
            timepoints are only visible to their owner.
        model_policy: ``"permissive"`` to force open-weight models only
            (Llama, DeepSeek, Qwen, etc).  Omit for the default policy.
        entity_ids: Optional list of Clockchain figure ids to pre-populate
            as characters (e.g.
            ``["/figures/person/julius-caesar"]``).
        request_context: Optional opaque dict echoed back in the response
            and the eventual callback/log trail.

    Returns:
        JSON-serializable dict with:
            * ``id`` — timepoint id; pass to the status endpoint.
            * ``status`` — ``"processing"`` on creation.
            * ``status_url`` — ready-to-curl Flash endpoint
              (``/api/v1/timepoints/{id}``).
            * ``slug`` — URL-friendly slug derived from the query.
            * ``owner_id`` — authenticated caller (or ``"mcp-anonymous"``).
            * ``query``, ``preset``, ``generate_image``, ``visibility`` —
              echoed configuration.
            * ``note`` — human-readable polling instructions.

        On validation failure, returns ``{"error": "<message>"}`` instead
        of raising so agents see a structured error rather than an MCP
        protocol error.
    """
    # Validate query length
    query = (query or "").strip()
    if not query:
        return {"error": "'query' is required and must be non-empty."}
    if len(query) < 3:
        return {"error": "'query' must be at least 3 characters."}
    if len(query) > 500:
        return {"error": "'query' must be at most 500 characters."}

    # Validate enum fields (empty → None, bad → error)
    normalized_preset, err = _validate_enum(preset, _ALLOWED_PRESETS, "preset")
    if err:
        return {"error": err}

    normalized_visibility, err = _validate_enum(visibility, _ALLOWED_VISIBILITIES, "visibility")
    if err:
        return {"error": err}

    normalized_policy, err = _validate_enum(model_policy, _ALLOWED_MODEL_POLICIES, "model_policy")
    if err:
        return {"error": err}

    # Build the generate request using the same schema the REST endpoint
    # uses so validation logic lives in one place.
    try:
        from app.api.v1.timepoints import GenerateRequest, resolve_model_policy

        req = GenerateRequest(
            query=query,
            generate_image=generate_image,
            preset=normalized_preset,
            text_model=(text_model or None),
            image_model=(image_model or None),
            visibility=normalized_visibility,
            model_policy=normalized_policy,
            entity_ids=entity_ids,
            request_context=request_context,
        )
    except (ValueError, TypeError) as exc:
        return {"error": f"Invalid generate request: {exc}"}

    # Resolve permissive policy into concrete model ids, mirroring the REST
    # endpoint exactly.  ``resolve_model_policy`` raises HTTPException(422)
    # on invalid combinations — catch and return as a structured error.
    try:
        resolved_text_model, resolved_image_model = resolve_model_policy(req)
    except Exception as exc:  # HTTPException or anything else
        detail = getattr(exc, "detail", None) or str(exc)
        return {"error": f"Invalid model configuration: {detail}"}

    user_id = _current_user()
    is_authenticated_user = bool(user_id) and user_id != "mcp-anonymous"

    # Deduct credits at the Gateway BEFORE we create any DB rows.  This
    # matches the REST endpoint semantics (credits charged on submission,
    # refunded on background failure) and mirrors the metering middleware
    # behaviour for the proxy path.  Gateway is the authoritative ledger
    # (see project_auth_consolidation.md); deducting here is what makes
    # MCP-initiated generations show up on /credits/balance.
    if is_authenticated_user:
        spent_ok, spend_err = await _gateway_spend_credits(
            user_id,
            cost=_GATEWAY_GENERATION_COST,
            description=f"mcp:tp_flash_generate ({normalized_preset or 'balanced'}): {query[:60]}",
        )
        if not spent_ok:
            return {"error": spend_err or "Credit deduction failed"}

    # Resolve the gateway user_id into a Flash users.id so the FK
    # constraint on timepoints.user_id is satisfied.  Auto-provisions a
    # Flash row when none exists for this identity.
    flash_user_id: str | None = None
    if is_authenticated_user:
        flash_user_id = await _resolve_or_provision_flash_user(user_id)
        if flash_user_id is None:
            # Don't strand the caller's credits — refund and surface a
            # structured error.
            await _gateway_refund_credits(
                user_id,
                _GATEWAY_GENERATION_COST,
                description=f"mcp:tp_flash_generate user-resolution-failed: {query[:60]}",
            )
            return {"error": "Failed to resolve user in Flash database"}

    # Create a PROCESSING timepoint row and schedule the pipeline.  We do
    # this in a short-lived session so we don't block the MCP request on
    # a full 30s generation.
    from app.api.v1.timepoints import run_generation_task
    from app.database import get_session
    from app.models import Timepoint, TimepointStatus, TimepointVisibility

    timepoint = Timepoint.create(
        query=query,
        status=TimepointStatus.PROCESSING,
    )
    if flash_user_id:
        timepoint.user_id = flash_user_id
    # Tag the row as MCP-originated so observability dashboards and the
    # background-task refund path can tell the two transports apart.
    timepoint.api_source = "mcp"
    if normalized_visibility:
        try:
            timepoint.visibility = TimepointVisibility(normalized_visibility)
        except ValueError:
            pass  # Keep default

    try:
        async with get_session() as session:
            session.add(timepoint)
            await session.commit()
            await session.refresh(timepoint)
    except Exception as exc:
        logger.exception("Failed to create timepoint row for MCP request")
        # Refund — we already deducted credits at the Gateway above.
        if is_authenticated_user:
            await _gateway_refund_credits(
                user_id,
                _GATEWAY_GENERATION_COST,
                description=f"mcp:tp_flash_generate timepoint-create-failed: {query[:60]}",
            )
        return {"error": f"Failed to create timepoint: {exc}"}

    # Fire-and-forget background generation.  We use asyncio.create_task
    # rather than FastAPI's BackgroundTasks because the MCP tool runs
    # outside of a FastAPI request context.  The task keeps a reference
    # in a module-level set so the loop doesn't garbage-collect it.
    coro = run_generation_task(
        timepoint.id,
        query,
        None,  # session_factory not needed with get_session()
        generate_image=generate_image,
        preset=normalized_preset,
        text_model=resolved_text_model,
        image_model=resolved_image_model,
        callback_url=None,
        request_context=request_context,
        model_policy=normalized_policy,
        llm_params=None,
        entity_ids=entity_ids,
        user_id=timepoint.user_id,
    )
    task = asyncio.create_task(coro)
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)

    vis_value = (
        timepoint.visibility.value
        if isinstance(timepoint.visibility, TimepointVisibility)
        else (timepoint.visibility or "public")
    )

    return {
        "id": timepoint.id,
        "status": "processing",
        "status_url": f"/api/v1/timepoints/{timepoint.id}",
        "slug": timepoint.slug,
        "owner_id": user_id,
        "query": query,
        "preset": normalized_preset or "balanced",
        "generate_image": generate_image,
        "visibility": vis_value,
        "note": (
            "Generation runs asynchronously — poll GET "
            f"https://flash.timepointai.com/api/v1/timepoints/{timepoint.id} "
            "(Authorization: Bearer <token>) for progress.  Typical "
            "generation completes in 5–60 seconds."
        ),
    }


# Keep references to scheduled background tasks so the event loop doesn't
# drop them mid-run.  Populated by :func:`tp_flash_generate`.
_BACKGROUND_TASKS: set[asyncio.Task[Any]] = set()


# ---------------------------------------------------------------------------
# Application wiring
# ---------------------------------------------------------------------------


def get_mcp_app():
    """Return the ASGI app for the MCP streamable HTTP transport.

    Mount this on the FastAPI app::

        app.mount("/mcp", BearerAuthMiddleware(get_mcp_app()))
    """
    return mcp.streamable_http_app()


def get_mcp_session_manager():
    """Return the MCP session manager for lifespan management.

    Call ``async with get_mcp_session_manager().run(): ...`` inside the
    FastAPI lifespan context so the streamable HTTP transport is started.
    """
    return mcp.session_manager
