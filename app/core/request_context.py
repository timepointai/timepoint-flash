"""Request-scoped context variables for cross-cutting concerns.

Uses Python contextvars so that async handlers running in the same task
share the same request context without passing it explicitly through every
call site.

Usage:
    # In middleware (set once per request)
    from app.core.request_context import set_request_id
    set_request_id(request.headers.get("X-Request-ID"))

    # Deep in the call stack (read anywhere)
    from app.core.request_context import get_request_id
    logger.info("llm_call ... request_id=%s", get_request_id() or "none")
"""

from __future__ import annotations

from contextvars import ContextVar

# Holds the X-Request-ID for the current request / background task.
# Default is None so callers never raise LookupError.
_request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def set_request_id(request_id: str | None) -> None:
    """Store the correlation ID in the current async context.

    Args:
        request_id: The X-Request-ID value from the incoming request,
            or None if the header was absent.
    """
    _request_id_var.set(request_id)


def get_request_id() -> str | None:
    """Return the correlation ID for the current async context.

    Returns:
        The X-Request-ID string, or None if not set.
    """
    return _request_id_var.get()
