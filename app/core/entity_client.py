"""HTTP client for Clockchain entity resolution API.

Resolves character names to persistent entity IDs via the Clockchain
figures batch-resolve endpoint. All failures are gracefully degraded
to empty results — entity resolution is optional.

Resolution modes:
- resolve_figures(): Returns simple {name: id} mapping (backward-compatible)
- resolve_figures_with_data(): Returns rich {name: FigureData} with grounding data
- fetch_figures_by_ids(): Fetch rich FigureData for known entity IDs
- search_figures(): Fuzzy search figures by display name (proxies to Clockchain)

Examples:
    >>> from app.core.entity_client import resolve_figures, fetch_figures_by_ids
    >>> mapping = await resolve_figures(["Julius Caesar", "Brutus"])
    >>> mapping
    {"Julius Caesar": "fig_abc123", "Brutus": "fig_def456"}
    >>> by_id = await fetch_figures_by_ids(["/figures/person/julius-caesar"])
    >>> by_id["/figures/person/julius-caesar"].display_name
    "Julius Caesar"

Tests:
    - tests/unit/test_entity_client.py
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import httpx

from app.config import settings
from app.schemas.entity_types import FigureData

logger = logging.getLogger(__name__)

# Timeouts: 5s connect, 10s read
_TIMEOUT = httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0)


def _get_base_url() -> str:
    """Return the base URL for entity resolution requests."""
    return settings.CLOCKCHAIN_ENTITY_URL or settings.CLOCKCHAIN_URL


def _get_headers(user_id: str | None = None) -> dict[str, str]:
    """Return auth headers for Clockchain requests.

    Args:
        user_id: Optional user ID to forward as X-User-ID for
                 visibility-filtered entity lookups.
    """
    headers: dict[str, str] = {"Content-Type": "application/json"}
    key = settings.CLOCKCHAIN_SERVICE_KEY
    if key:
        headers["X-Service-Key"] = key
    if user_id:
        headers["X-User-ID"] = user_id
    return headers


async def resolve_figures(
    names: list[str],
    entity_type: str = "person",
    user_id: str | None = None,
) -> dict[str, str]:
    """Resolve character names to Clockchain entity IDs.

    Calls POST /api/v1/figures/resolve/batch on the Clockchain (or Gateway).
    Returns an empty dict on any failure — entity resolution must never
    block generation.

    Args:
        names: List of character names to resolve.
        entity_type: Entity type hint (default "person").
        user_id: Optional user ID forwarded as X-User-ID for visibility filtering.

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
                headers=_get_headers(user_id=user_id),
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


async def resolve_figures_with_data(
    names: list[str],
    entity_type: str = "person",
    user_id: str | None = None,
) -> dict[str, FigureData]:
    """Resolve names to Clockchain figures with full grounding data.

    Calls the same /api/v1/figures/resolve/batch endpoint as resolve_figures()
    but parses the full response into FigureData objects.

    Returns {display_name: FigureData} where FigureData includes grounding
    status, confidence, external_ids, aliases, etc.

    All failures are gracefully degraded to empty results.

    Args:
        names: List of character names to resolve.
        entity_type: Entity type hint (default "person").
        user_id: Optional user ID forwarded as X-User-ID for visibility filtering.

    Returns:
        Mapping of {display_name: FigureData} for successfully resolved names.
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
                headers=_get_headers(user_id=user_id),
            )
            response.raise_for_status()
            data = response.json()

            results: list[dict] = data.get("results", [])
            resolved: dict[str, FigureData] = {}
            for item in results:
                figure = item.get("figure", {})
                display_name = figure.get("display_name", "")
                figure_id = figure.get("id", "")
                if display_name and figure_id:
                    resolved[display_name] = FigureData.from_api_response(figure)

            grounded_count = sum(1 for f in resolved.values() if f.is_grounded)
            logger.debug(
                f"Entity resolution (rich): {len(resolved)}/{len(names)} resolved, "
                f"{grounded_count} grounded"
            )
            return resolved

    except httpx.TimeoutException:
        logger.warning("Entity resolution (rich) timed out — continuing without entity data")
        return {}
    except httpx.HTTPStatusError as exc:
        logger.warning(
            f"Entity resolution (rich) HTTP {exc.response.status_code} — continuing without entity data"
        )
        return {}
    except Exception:
        logger.warning("Entity resolution (rich) failed — continuing without entity data", exc_info=True)
        return {}


async def fetch_figures_by_ids(
    entity_ids: list[str],
    user_id: str | None = None,
) -> dict[str, FigureData]:
    """Fetch rich FigureData for known Clockchain entity IDs.

    Calls GET /api/v1/figures/{id} for each entity_id in parallel.
    Used by the entity library flow where the caller already has figure IDs
    from a previous search or selection.

    All failures are gracefully degraded — missing or failed IDs are omitted.

    Args:
        entity_ids: List of Clockchain figure IDs (e.g. "/figures/person/julius-caesar").
        user_id: Optional user ID forwarded as X-User-ID for visibility filtering.

    Returns:
        Mapping of {entity_id: FigureData} for successfully fetched figures.
    """
    if not entity_ids:
        return {}

    base_url = _get_base_url()
    if not base_url:
        logger.debug(
            "Entity fetch skipped: no CLOCKCHAIN_ENTITY_URL or CLOCKCHAIN_URL configured"
        )
        return {}

    req_headers = _get_headers(user_id=user_id)

    async def _fetch_one(client: httpx.AsyncClient, entity_id: str) -> tuple[str, FigureData | None]:
        """Fetch a single figure by ID."""
        # Clockchain expects the ID path without leading slash in the URL
        clean_id = entity_id.lstrip("/")
        url = f"{base_url.rstrip('/')}/api/v1/figures/{clean_id}"
        try:
            response = await client.get(url, headers=req_headers)
            response.raise_for_status()
            figure = response.json()
            return entity_id, FigureData.from_api_response(figure)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                logger.debug(f"Entity {entity_id} not found in Clockchain")
            else:
                logger.warning(f"Entity fetch HTTP {exc.response.status_code} for {entity_id}")
            return entity_id, None
        except Exception:
            logger.warning(f"Entity fetch failed for {entity_id}", exc_info=True)
            return entity_id, None

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            tasks = [_fetch_one(client, eid) for eid in entity_ids]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            resolved: dict[str, FigureData] = {}
            for result in results:
                if isinstance(result, Exception):
                    continue
                entity_id, figure_data = result
                if figure_data is not None:
                    resolved[entity_id] = figure_data

            grounded_count = sum(1 for f in resolved.values() if f.is_grounded)
            logger.debug(
                f"Entity fetch by ID: {len(resolved)}/{len(entity_ids)} fetched, "
                f"{grounded_count} grounded"
            )
            return resolved

    except Exception:
        logger.warning("Entity fetch by IDs failed", exc_info=True)
        return {}


async def search_figures(
    query: str,
    entity_type: str | None = None,
    limit: int = 20,
    user_id: str | None = None,
) -> list[dict]:
    """Search Clockchain figures by display name.

    Proxies to GET /api/v1/figures/search on Clockchain for fuzzy search.
    Returns raw search results for the autocomplete UX.

    Args:
        query: Search query string.
        entity_type: Optional entity type filter (person, organization, place).
        limit: Maximum results to return (default 20, max 100).
        user_id: Optional user ID forwarded as X-User-ID for visibility filtering.

    Returns:
        List of search result dicts with id, display_name, entity_type, score.
        Empty list on any failure.
    """
    base_url = _get_base_url()
    if not base_url:
        logger.debug("Entity search skipped: no CLOCKCHAIN_URL configured")
        return []

    url = f"{base_url.rstrip('/')}/api/v1/figures/search"
    params: dict[str, str | int] = {"q": query, "limit": limit}
    if entity_type:
        params["entity_type"] = entity_type

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.get(url, params=params, headers=_get_headers(user_id=user_id))
            response.raise_for_status()
            results = response.json()
            logger.debug(f"Entity search '{query}': {len(results)} results")
            return results

    except httpx.TimeoutException:
        logger.warning("Entity search timed out")
        return []
    except httpx.HTTPStatusError as exc:
        logger.warning(f"Entity search HTTP {exc.response.status_code}")
        return []
    except Exception:
        logger.warning("Entity search failed", exc_info=True)
        return []


async def ground_figure(
    figure_id: str,
    grounding_status: str = "grounded",
    grounding_model: str = "",
    grounding_confidence: float | None = None,
    grounding_sources: list[str] | None = None,
    grounded_at: datetime | None = None,
    user_id: str | None = None,
) -> bool:
    """Update a Clockchain figure's grounding metadata via PATCH /ground.

    Returns True on success, False on any failure — grounding updates
    must never block the caller.

    Args:
        figure_id: Clockchain figure ID.
        grounding_status: New grounding status.
        grounding_model: Model used for grounding.
        grounding_confidence: Confidence score.
        grounding_sources: List of source URLs.
        grounded_at: Timestamp of grounding.
        user_id: Optional user ID forwarded as X-User-ID for ownership verification.
    """
    base_url = _get_base_url()
    if not base_url:
        logger.debug("Figure grounding skipped: no CLOCKCHAIN_URL configured")
        return False

    if not figure_id:
        logger.debug("Figure grounding skipped: no figure_id provided")
        return False

    if grounded_at is None:
        grounded_at = datetime.now(timezone.utc)

    clean_id = figure_id.lstrip("/")
    url = f"{base_url.rstrip('/')}/api/v1/figures/{clean_id}/ground"
    payload: dict = {
        "grounding_status": grounding_status,
        "grounded_at": grounded_at.isoformat(),
    }
    if grounding_model:
        payload["grounding_model"] = grounding_model
    if grounding_confidence is not None:
        payload["grounding_confidence"] = grounding_confidence
    if grounding_sources is not None:
        payload["grounding_sources"] = grounding_sources

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.patch(url, json=payload, headers=_get_headers(user_id=user_id))
            response.raise_for_status()
            logger.debug(f"Figure grounding updated: {figure_id} → {grounding_status}")
            return True

    except httpx.TimeoutException:
        logger.warning(f"Figure grounding timed out for {figure_id}")
        return False
    except httpx.HTTPStatusError as exc:
        logger.warning(f"Figure grounding HTTP {exc.response.status_code} for {figure_id}")
        return False
    except Exception:
        logger.warning(f"Figure grounding failed for {figure_id}", exc_info=True)
        return False
