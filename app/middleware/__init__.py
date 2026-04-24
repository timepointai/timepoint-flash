"""API middleware modules.

Currently provides Bearer-token authentication for the MCP sub-app.  The
HTTP-level middlewares (CorrelationIDMiddleware, GatewayAuthMiddleware) are
defined in :mod:`app.main` because they rely on FastAPI's request model;
this package is reserved for **ASGI**-level middlewares that wrap mounted
sub-apps (e.g. the MCP Streamable HTTP server at ``/mcp``).
"""

from .bearer_auth import (
    BearerAuthMiddleware,
    current_bearer_user,
    extract_bearer_token,
    get_current_bearer_user,
    verify_bearer_token,
)

__all__ = [
    "BearerAuthMiddleware",
    "current_bearer_user",
    "extract_bearer_token",
    "get_current_bearer_user",
    "verify_bearer_token",
]
