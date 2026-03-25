"""HTTP client for Clockchain entity resolution API.

Resolves character names to persistent entity IDs via the Clockchain
figures batch-resolve endpoint. All failures are gracefully degraded
to empty results — entity resolution is optional.

Examples:
    >>> from app.core.entity_client import resolve_figures
    >>> mapping = await resolve_figures(["Julius Caesar", "Brutus"])
    >>> mapping
    {"Julius Caesar": "fig_abc123", "Brutus": "fig_def456"}

Tests:
    - tests/unit/test_entity_client.py
"""

from __future__ import annotations

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Timeouts: 5s connect, 10s read
_TIMEOUT = httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0)


def _get_base_url() -> str:
    """Return the base URL for entity resolution requests."""
    return settings.CLOCKCHAIN_ENTITY_URL or settings.CLOCKCHAIN_URL


def _get_headers() -> dict[str, str]:
    """Return auth headers for Clockchain requests."""
    headers: dict[str, str] = {"Content-Type": "application/json"}
    key = settings.CLOCKCHAIN_SERVICE_KEY
    if key:
        headers["X-Service-Key"] = key
    return headers


async def resolve_figures(
    names: list[str],
    entity_type: str = "person",
) -> dict[str, str]:
    """Resolve character names to Clockchain entity IDs.

    Calls POST /api/v1/figures/resolve/batch on the Clockchain (or Gateway).
    Returns an empty dict on any failure — entity resolution must never
    block generation.

    Args:
        names: List of character names to resolve.
        entity_type: Entity type hint (default "person").

    Returns:
        Mapping of {name: entity_id} for successfully resolved names.
    """
    if not names:
        return {}

    base_url = _get_base_url()
    if not base_url:
        logger.debug(
            "Entity resolution skipped: no CLOCKCHAIN_ENTITY_URL or CLOCKCHAIN_URL configured"
        )
        return {}

    url = f"{base_url.rstrip('/')}/api/v1/figures/resolve/batch"

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(
                url,
                json={"names": [{"display_name": n, "entity_type": entity_type} for n in names]},
                headers=_get_headers(),
            )
            response.raise_for_status()
            data = response.json()

            # Response: {"results": [{"figure": {"id": "...", "display_name": "..."}, "created": bool}, ...]}
            results: list[dict] = data.get("results", [])
            resolved: dict[str, str] = {}
            for item in results:
                figure = item.get("figure", {})
                display_name = figure.get("display_name", "")
                figure_id = figure.get("id", "")
                if display_name and figure_id:
                    resolved[display_name] = figure_id
            logger.debug(f"Entity resolution: {len(resolved)}/{len(names)} names resolved")
            return resolved

    except httpx.TimeoutException:
        logger.warning("Entity resolution timed out — continuing without entity IDs")
        return {}
    except httpx.HTTPStatusError as exc:
        logger.warning(
            f"Entity resolution HTTP {exc.response.status_code} — continuing without entity IDs"
        )
        return {}
    except Exception:
        logger.warning("Entity resolution failed — continuing without entity IDs", exc_info=True)
        return {}
