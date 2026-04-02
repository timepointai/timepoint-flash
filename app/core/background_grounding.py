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
    ...     user_id="user_xyz",
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
        import httpx

        if not settings.OPENROUTER_API_KEY:
            logger.debug(
                f"Background grounding skipped for '{entity_name}': no OPENROUTER_API_KEY"
            )
            return existing_profile

        # Use direct OpenRouter call with deeper search (more results than pipeline pass)
        grounding_model = "perplexity/sonar"
        prompt = (
            f"Research {entity_name} in depth. Provide: detailed biographical summary, "
            f"physical appearance description, all known affiliations and roles, "
            f"recent notable activity. Be thorough and cite sources."
        )

        payload: dict[str, Any] = {
            "model": grounding_model,
            "messages": [
                {"role": "system", "content": "You are a research assistant. Provide factual, well-sourced information."},
                {"role": "user", "content": prompt},
            ],
            "plugins": [{"id": "web", "max_results": _DEEP_MAX_RESULTS}],
            "temperature": 0.2,
            "max_tokens": 2048,
        }

        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

        message = data["choices"][0]["message"]
        biography_text: str = message.get("content") or ""

        if not biography_text:
            return existing_profile

        # Extract citations from annotations
        annotations = message.get("annotations", [])
        citations = []
        for ann in annotations:
            url_citation = ann.get("url_citation", {})
            url = url_citation.get("url", "")
            if url:
                citations.append(url)

        enriched = GroundingProfile(
            entity_name=entity_name,
            entity_id=existing_profile.entity_id,
            grounding_model=grounding_model,
            grounded_at=datetime.now(UTC),
            biography_summary=biography_text[:2000],
            appearance_description=existing_profile.appearance_description,
            known_affiliations=existing_profile.known_affiliations,
            recent_activity_summary="",
            source_citations=citations or existing_profile.source_citations,
            confidence=min(existing_profile.confidence + 0.1, 1.0),
        )

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
    user_id: str | None = None,
) -> None:
    """PATCH a Clockchain figure with grounding metadata from a GroundingProfile.

    No-op if the profile has no entity_id.

    Args:
        entity_name: Human-readable name (for logging).
        profile: The grounding profile with entity_id and metadata.
        semaphore: Concurrency limiter.
        user_id: Optional user ID forwarded as X-User-ID for visibility filtering.
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
            user_id=user_id,
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
    user_id: str | None = None,
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
        user_id: Optional user ID forwarded as X-User-ID to Clockchain
                 for visibility-filtered entity lookups.
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
        _patch_clockchain_figure(name, profile, semaphore, user_id=user_id)
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
