"""Post-generation background grounding task.

After a timepoint is generated and returned to the user, this module runs
a deeper entity grounding pass and syncs results back to Clockchain and
the Flash timepoint record.

The task is non-blocking — it runs asynchronously after the generation
response has been sent. All failures are logged but never propagate.

Flow:
    1. Re-run EntityGroundingAgent with deeper search (more results, X data)
    2. PATCH each figure's grounding metadata on Clockchain
    3. Update the Flash timepoint tdf_payload with enriched grounding_data

Gated behind ENTITY_GROUNDING_BACKGROUND_ENABLED env var (default false).

Examples:
    >>> from app.core.background_grounding import run_background_grounding
    >>> # Fire and forget — does not block
    >>> import asyncio
    >>> asyncio.create_task(run_background_grounding(
    ...     timepoint_id="tp_abc123",
    ...     entity_profiles={"Marc Andreessen": profile},
    ... ))

Tests:
    - tests/unit/test_background_grounding.py
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from app.config import settings
from app.core.entity_client import ground_figure
from app.schemas.grounding_profile import GroundingProfile

logger = logging.getLogger(__name__)

# Deeper pass: more search results than the initial pipeline pass
_DEEP_MAX_RESULTS = 10

# Max concurrent Clockchain PATCH calls
_MAX_CONCURRENT_PATCHES = 3


async def _deep_ground_entity(
    entity_name: str,
    existing_profile: GroundingProfile,
) -> GroundingProfile:
    """Run a deeper grounding pass for a single entity.

    Calls OpenRouter with a higher max_results budget than the initial pass.
    Falls back to the existing profile on any failure.

    Args:
        entity_name: The entity name to re-ground.
        existing_profile: Profile from the initial pipeline pass.

    Returns:
        Enriched GroundingProfile (or the original on failure).
    """
    try:
        from app.agents.entity_grounding import (
            GROUNDING_MODEL,
            _call_grok_x_search,
            _call_openrouter_web_search,
            _parse_biography_text,
        )

        # Re-run web search with higher max_results
        import httpx

        from app.agents.entity_grounding import (
            ENTITY_RESEARCH_SYSTEM,
            GROK_MODEL,
            OPENROUTER_BASE_URL,
            OPENROUTER_TIMEOUT,
            _build_entity_research_prompt,
            _extract_annotations,
            _get_openrouter_headers,
        )

        if not settings.OPENROUTER_API_KEY:
            logger.debug(
                f"Background grounding skipped for '{entity_name}': no OPENROUTER_API_KEY"
            )
            return existing_profile

        payload: dict[str, Any] = {
            "model": GROUNDING_MODEL,
            "messages": [
                {"role": "system", "content": ENTITY_RESEARCH_SYSTEM},
                {"role": "user", "content": _build_entity_research_prompt(entity_name)},
            ],
            "plugins": [{"id": "web", "max_results": _DEEP_MAX_RESULTS}],
            "temperature": 0.2,
            "max_tokens": 2048,
        }

        async with httpx.AsyncClient(
            base_url=OPENROUTER_BASE_URL,
            timeout=OPENROUTER_TIMEOUT,
            headers=_get_openrouter_headers(),
        ) as client:
            resp = await client.post("/chat/completions", json=payload)
            resp.raise_for_status()
            data = resp.json()

        message = data["choices"][0]["message"]
        biography_text: str = message.get("content") or ""
        search_results = _extract_annotations(message)

        if not biography_text:
            return existing_profile

        enriched = _parse_biography_text(
            entity_name=entity_name,
            text=biography_text,
            search_results=search_results,
            entity_id=existing_profile.entity_id,
            model=GROUNDING_MODEL,
        )

        # Carry over X posts if we already have them
        if existing_profile.x_posts and not enriched.x_posts:
            enriched.x_posts = existing_profile.x_posts

        logger.debug(
            f"Background grounding: deep pass for '{entity_name}' "
            f"confidence={enriched.confidence:.2f} sources={len(enriched.source_citations)}"
        )
        return enriched

    except Exception:
        logger.warning(
            f"Background grounding deep pass failed for '{entity_name}' — using initial profile",
            exc_info=True,
        )
        return existing_profile


async def _patch_clockchain_figure(
    entity_name: str,
    profile: GroundingProfile,
    semaphore: asyncio.Semaphore,
) -> None:
    """PATCH a Clockchain figure with grounding metadata from a GroundingProfile.

    No-op if the profile has no entity_id.

    Args:
        entity_name: Human-readable name (for logging).
        profile: The grounding profile with entity_id and metadata.
        semaphore: Concurrency limiter.
    """
    if not profile.entity_id:
        logger.debug(
            f"Background grounding: no entity_id for '{entity_name}' — skipping Clockchain PATCH"
        )
        return

    async with semaphore:
        ok = await ground_figure(
            figure_id=profile.entity_id,
            grounding_status="grounded",
            grounding_model=profile.grounding_model,
            grounding_confidence=profile.confidence,
            grounding_sources=profile.source_citations,
            grounded_at=profile.grounded_at,
        )
        if ok:
            logger.info(
                f"Background grounding: Clockchain figure updated for '{entity_name}' "
                f"(id={profile.entity_id})"
            )
        else:
            logger.warning(
                f"Background grounding: Clockchain PATCH failed for '{entity_name}' "
                f"(id={profile.entity_id}) — continuing"
            )


async def _update_flash_timepoint(
    timepoint_id: str,
    enriched_profiles: dict[str, GroundingProfile],
) -> None:
    """Update the Flash timepoint record with enriched entity grounding data.

    Merges enriched profiles into tdf_payload["entity_grounding_data"].

    Args:
        timepoint_id: Flash timepoint ID to update.
        enriched_profiles: Mapping of {entity_name: GroundingProfile}.
    """
    try:
        from sqlalchemy import select

        from app.database import get_session
        from app.models import Timepoint

        enriched_data: dict[str, Any] = {
            name: profile.model_dump(mode="json")
            for name, profile in enriched_profiles.items()
        }

        async with get_session() as session:
            result = await session.execute(
                select(Timepoint).where(Timepoint.id == timepoint_id)
            )
            tp = result.scalar_one_or_none()
            if tp is None:
                logger.warning(
                    f"Background grounding: timepoint {timepoint_id} not found — skipping update"
                )
                return

            payload = dict(tp.tdf_payload or {})
            payload["entity_grounding_data"] = enriched_data
            payload["entity_grounding_completed_at"] = datetime.now(UTC).isoformat()
            tp.tdf_payload = payload
            await session.commit()
            logger.info(
                f"Background grounding: Flash timepoint {timepoint_id} updated with "
                f"{len(enriched_profiles)} enriched profiles"
            )
    except Exception:
        logger.warning(
            f"Background grounding: Flash timepoint update failed for {timepoint_id}",
            exc_info=True,
        )


async def run_background_grounding(
    timepoint_id: str,
    entity_profiles: dict[str, GroundingProfile],
) -> None:
    """Run post-generation background grounding for a completed timepoint.

    This is the main entry point for background grounding. It:
    1. Runs a deeper grounding pass for each entity (more search results).
    2. PATCHes Clockchain figure records with the enriched metadata.
    3. Updates the Flash timepoint tdf_payload with enriched grounding_data.

    All steps are non-fatal — failures are logged and the task continues.
    The caller should fire this with asyncio.create_task() to avoid blocking.

    Args:
        timepoint_id: Flash timepoint ID for the completed generation.
        entity_profiles: Initial grounding profiles from the pipeline pass,
                         keyed by entity name.
    """
    if not entity_profiles:
        logger.debug(
            f"Background grounding: no entity profiles for {timepoint_id} — skipping"
        )
        return

    logger.info(
        f"Background grounding: starting for {timepoint_id} "
        f"({len(entity_profiles)} entities)"
    )

    # Step 1: Run deeper grounding passes
    enriched_profiles: dict[str, GroundingProfile] = {}
    for entity_name, profile in entity_profiles.items():
        enriched = await _deep_ground_entity(entity_name, profile)
        enriched_profiles[entity_name] = enriched

    # Step 2: PATCH Clockchain figure records (concurrently)
    semaphore = asyncio.Semaphore(_MAX_CONCURRENT_PATCHES)
    patch_tasks = [
        _patch_clockchain_figure(name, profile, semaphore)
        for name, profile in enriched_profiles.items()
    ]
    if patch_tasks:
        await asyncio.gather(*patch_tasks, return_exceptions=True)

    # Step 3: Update Flash timepoint with enriched grounding data
    await _update_flash_timepoint(timepoint_id, enriched_profiles)

    logger.info(
        f"Background grounding: completed for {timepoint_id} "
        f"({len(enriched_profiles)} entities enriched)"
    )
