"""Bearer-token authentication for the Flash MCP sub-app.

The Flash MCP server at ``/mcp/`` accepts ``Authorization: Bearer <token>`` and
resolves the token to a ``user_id`` using two strategies (tried in order):

1. **Static environment list** — ``FLASH_MCP_BEARER_TOKENS`` env var, comma
   separated. Each entry is either ``<token>`` or ``<token>:<user_id>``.
   When no user_id is specified, a deterministic ``bearer-<prefix>`` id is
   derived from the token.  This is the primary mechanism for local dev,
   CI fixtures, and service-to-service tokens minted out-of-band.

2. **Gateway-issued user keys (``tp_gw_*`` / ``tp_org_*``)** — when the
   token starts with the Gateway's key prefix and the Flash service is
   configured with ``GATEWAY_INTERNAL_URL`` + ``GATEWAY_SERVICE_KEY``, the
   middleware calls the Gateway's ``/internal/auth/validate-key`` endpoint
   to resolve the owning user.  This lets MCP clients use the same API key
   they already use for REST calls.  If the Gateway is unreachable or the
   service key is not configured, this path is simply skipped.

The :class:`BearerAuthMiddleware` is an ASGI middleware mounted in front of
the MCP sub-app.  It extracts the token, verifies it, stores the resolved
``user_id`` in the :data:`current_bearer_user` ``ContextVar`` so MCP tools
can read it, and returns 401 for missing / invalid tokens.  ``OPTIONS``
preflight requests pass through unauthenticated so browser MCP clients can
complete CORS negotiation.
"""

from __future__ import annotations

import json
import logging
import os
from contextvars import ContextVar

import httpx
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Context variable for tool access
# ---------------------------------------------------------------------------

# Set by :class:`BearerAuthMiddleware` before dispatching to the MCP sub-app,
# read by MCP tools via :func:`get_current_bearer_user`.  Uses a ContextVar so
# concurrent async requests don't see each other's user_id.
current_bearer_user: ContextVar[str | None] = ContextVar("current_bearer_user", default=None)


def get_current_bearer_user() -> str | None:
    """Return the user_id of the Bearer token for the current request.

    Returns ``None`` if no Bearer token was validated (e.g. the request came
    through a different transport or the middleware wasn't applied).
    """
    return current_bearer_user.get()


# ---------------------------------------------------------------------------
# Static-token parsing
# ---------------------------------------------------------------------------


_GATEWAY_KEY_PREFIXES: tuple[str, ...] = ("tp_gw_", "tp_org_")


def _parse_static_tokens() -> dict[str, str]:
    """Parse the ``FLASH_MCP_BEARER_TOKENS`` env var.

    Entries are comma-separated.  Each entry is either ``<token>`` (user_id is
    derived as ``bearer-<first-8-chars-of-token>``) or ``<token>:<user_id>``.

    Returns:
        Dict mapping token → user_id.  Empty dict if env var is unset.
    """
    raw = os.environ.get("FLASH_MCP_BEARER_TOKENS", "")
    tokens: dict[str, str] = {}
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        if ":" in entry:
            tok, uid = entry.split(":", 1)
            tok = tok.strip()
            uid = uid.strip()
        else:
            tok = entry
            uid = f"bearer-{tok[:8]}"
        if tok:
            tokens[tok] = uid
    return tokens


# ---------------------------------------------------------------------------
# Gateway introspection
# ---------------------------------------------------------------------------


async def _verify_via_gateway(token: str) -> str | None:
    """Validate a ``tp_gw_*`` / ``tp_org_*`` token via the Gateway.

    Calls ``POST {GATEWAY_INTERNAL_URL}/internal/auth/validate-key`` using
    ``X-Service-Key: {GATEWAY_SERVICE_KEY}``.  Returns the owning ``user_id``
    on success, ``None`` otherwise.  All network errors are swallowed and
    logged — the middleware falls back to rejecting the token.
    """
    gateway_url = os.environ.get("GATEWAY_INTERNAL_URL", "").rstrip("/")
    service_key = os.environ.get("GATEWAY_SERVICE_KEY", "")

    if not gateway_url or not service_key:
        return None

    url = f"{gateway_url}/internal/auth/validate-key"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                url,
                json={"key": token},
                headers={"X-Service-Key": service_key},
            )
    except (httpx.HTTPError, OSError) as exc:
        logger.warning("Gateway key introspection failed: %s", exc)
        return None

    if response.status_code != 200:
        return None

    try:
        data = response.json()
    except ValueError:
        return None

    user_id = data.get("user_id") if isinstance(data, dict) else None
    return user_id if isinstance(user_id, str) and user_id else None


# ---------------------------------------------------------------------------
# Bearer token verification
# ---------------------------------------------------------------------------


async def verify_bearer_token(token: str) -> str | None:
    """Verify a Bearer token and return the associated ``user_id``.

    Checked in order:

    1. ``FLASH_MCP_BEARER_TOKENS`` static env var.
    2. Gateway key introspection for ``tp_gw_*`` / ``tp_org_*`` tokens (when
       ``GATEWAY_INTERNAL_URL`` and ``GATEWAY_SERVICE_KEY`` are configured).

    Args:
        token: The raw token extracted from the ``Authorization`` header.

    Returns:
        ``user_id`` on success, ``None`` if the token is unknown or empty.
    """
    if not token:
        return None

    # 1. Static env-configured tokens
    static = _parse_static_tokens()
    if token in static:
        return static[token]

    # 2. Gateway-issued user keys (tp_gw_* / tp_org_*)
    if token.startswith(_GATEWAY_KEY_PREFIXES):
        return await _verify_via_gateway(token)

    return None


def extract_bearer_token(headers: list[tuple[bytes, bytes]]) -> str | None:
    """Extract a Bearer token from ASGI-style headers.

    Args:
        headers: The ``scope["headers"]`` list (raw bytes tuples).

    Returns:
        The token if present and well-formed, else ``None``.
    """
    for name, value in headers:
        if name.lower() != b"authorization":
            continue
        try:
            decoded = value.decode("latin-1")
        except UnicodeDecodeError:
            return None
        parts = decoded.strip().split(None, 1)
        if len(parts) != 2:
            return None
        scheme, credential = parts
        if scheme.lower() != "bearer":
            return None
        credential = credential.strip()
        return credential or None
    return None


# ---------------------------------------------------------------------------
# ASGI middleware — protects the MCP sub-app
# ---------------------------------------------------------------------------


class BearerAuthMiddleware:
    """ASGI middleware that enforces ``Authorization: Bearer <token>``.

    Mounted in front of the MCP sub-app so unauthorized requests never reach
    the tool dispatcher.  Stores the resolved ``user_id`` in the
    :data:`current_bearer_user` contextvar for downstream tool handlers.

    Behaviour:

    * ``OPTIONS`` preflights pass through unauthenticated so browser-based
      MCP clients can complete CORS negotiation.
    * Requests without a Bearer header or with an unrecognised token return
      401 JSON with a ``WWW-Authenticate: Bearer`` header.
    * Lifespan / websocket / other non-HTTP scopes pass through unchanged.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            # Lifespan / websocket / other: pass through.
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "").upper()
        if method == "OPTIONS":
            await self.app(scope, receive, send)
            return

        token = extract_bearer_token(scope.get("headers") or [])
        if token is None:
            await _send_401(
                send,
                "Missing Authorization header. "
                "Pass 'Authorization: Bearer <token>' to call the Flash MCP server.",
            )
            return

        user_id = await verify_bearer_token(token)
        if user_id is None:
            await _send_401(send, "Invalid or unrecognized Bearer token.")
            return

        reset_token = current_bearer_user.set(user_id)
        try:
            await self.app(scope, receive, send)
        finally:
            current_bearer_user.reset(reset_token)


async def _send_401(send: Send, detail: str) -> None:
    """Emit a 401 response with a JSON error body."""
    body = json.dumps(
        {
            "error": "Unauthorized",
            "message": detail,
            "www_authenticate": 'Bearer realm="timepoint-flash-mcp"',
        }
    ).encode("utf-8")

    await send(
        {
            "type": "http.response.start",
            "status": 401,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("latin-1")),
                (b"www-authenticate", b'Bearer realm="timepoint-flash-mcp"'),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body, "more_body": False})
