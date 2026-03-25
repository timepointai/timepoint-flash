"""PostHog server-side feature flag utilities for Flash.

Feature flags allow gradual rollout of pipeline features and experimental
capabilities without redeployment. When POSTHOG_API_KEY is not set, all
flags default to False (safe/off state).

Usage:
    from app.feature_flags import is_feature_enabled

    enabled = await is_feature_enabled("entity-persistence", distinct_id=user_id)

Feature flags in use:
    entity-persistence   — enables Phase 2+ entity registry writes during generation
    high-quality-preset  — enables the high-quality pipeline preset for opted-in users
"""

from __future__ import annotations

import asyncio
import logging
from functools import partial

logger = logging.getLogger(__name__)

_initialized = False


def init_posthog() -> None:
    """Initialize PostHog SDK. Safe to call multiple times."""
    global _initialized
    from app.config import get_settings

    settings = get_settings()
    if not settings.POSTHOG_API_KEY:
        logger.info("POSTHOG_API_KEY not set — PostHog feature flags disabled")
        return

    try:
        import posthog

        posthog.api_key = settings.POSTHOG_API_KEY
        posthog.host = settings.POSTHOG_HOST
        posthog.disabled = False
        _initialized = True
        logger.info("PostHog initialized (host=%s)", settings.POSTHOG_HOST)
    except ImportError:
        logger.warning("posthog package not installed — feature flags disabled")


async def is_feature_enabled(flag: str, distinct_id: str = "anonymous") -> bool:
    """Check a PostHog feature flag asynchronously.

    Runs the blocking PostHog SDK call in a thread pool executor so it does not
    block the async event loop. Returns False on any error or when PostHog is
    not configured — callers must treat False as the safe/disabled state.

    Args:
        flag: Feature flag key as defined in PostHog dashboard.
        distinct_id: User or entity identifier for percentage rollout targeting.

    Returns:
        True if the flag is enabled for the given distinct_id, False otherwise.
    """
    if not _initialized:
        return False

    try:
        import posthog

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            partial(posthog.is_feature_enabled, flag, distinct_id),
        )
        return bool(result)
    except Exception:
        logger.warning("PostHog flag check failed for '%s' (distinct_id=%s)", flag, distinct_id)
        return False


def shutdown_posthog() -> None:
    """Flush pending PostHog events on shutdown."""
    if not _initialized:
        return
    try:
        import posthog

        posthog.shutdown()
    except Exception:
        pass
