"""Entity search API endpoints.

Provides entity autocomplete for the generation form by proxying
to the Clockchain figures search endpoint.

Endpoints:
    GET /api/v1/entities/search?q={query} - Search entities by name

Examples:
    >>> GET /api/v1/entities/search?q=julius
    >>> [{"id": "/figures/person/julius-caesar", "display_name": "Julius Caesar", ...}]

Tests:
    - tests/unit/test_api_entities.py
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.entity_client import search_figures

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/entities", tags=["entities"])


class EntitySearchResult(BaseModel):
    """A single entity search result.

    Attributes:
        id: Clockchain figure ID.
        display_name: Canonical display name.
        entity_type: Entity type (person, organization, place, etc.).
        score: Fuzzy match score from Clockchain.
    """

    id: str
    display_name: str
    entity_type: str = "person"
    score: float = 0.0


class EntitySearchResponse(BaseModel):
    """Response from entity search endpoint.

    Attributes:
        results: List of matching entities.
        query: The search query that was used.
        total: Number of results returned.
    """

    results: list[EntitySearchResult]
    query: str
    total: int


@router.get("/search", response_model=EntitySearchResponse)
async def search_entities(
    q: str = Query(
        ...,
        min_length=1,
        max_length=200,
        description="Search query for entity name (fuzzy match)",
    ),
    entity_type: str | None = Query(
        default=None,
        description="Filter by entity type: person, organization, place",
    ),
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of results",
    ),
) -> EntitySearchResponse:
    """Search entities by name for autocomplete.

    Proxies to Clockchain figures search endpoint with fuzzy matching.
    Used by the generation form to offer entity library autocomplete.

    Args:
        q: Search query string.
        entity_type: Optional entity type filter.
        limit: Maximum results to return.

    Returns:
        EntitySearchResponse with matching entities.

    Raises:
        HTTPException: 503 if Clockchain is unavailable.
    """
    results = await search_figures(query=q, entity_type=entity_type, limit=limit)

    return EntitySearchResponse(
        results=[
            EntitySearchResult(
                id=r.get("id", ""),
                display_name=r.get("display_name", ""),
                entity_type=r.get("entity_type", "person"),
                score=r.get("score", 0.0),
            )
            for r in results
        ],
        query=q,
        total=len(results),
    )
