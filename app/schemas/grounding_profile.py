"""Grounding profile schemas for entity enrichment via web search.

Stores structured grounding data for entities (people, organizations, places)
enriched through OpenRouter web search plugins (Perplexity Sonar, xAI Grok).

Examples:
    >>> from app.schemas.grounding_profile import GroundingProfile
    >>> profile = GroundingProfile(
    ...     entity_name="Marc Andreessen",
    ...     grounding_model="perplexity/sonar",
    ...     grounded_at=datetime.now(timezone.utc),
    ...     biography_summary="Co-founder of Andreessen Horowitz...",
    ...     appearance_description="Tall, bald, known for casual attire",
    ...     known_affiliations=["Andreessen Horowitz", "Mosaic"],
    ...     recent_activity_summary="Active in AI investment...",
    ...     source_citations=["https://a16z.com/about"],
    ...     confidence=0.92,
    ... )
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    """A single web search result returned from OpenRouter annotations.

    Attributes:
        title: Title of the search result page.
        url: URL of the source.
        snippet: Relevant text snippet from the source.
        relevance: Relevance score (0.0-1.0), estimated from position/context.
    """

    title: str = Field(default="", description="Title of the search result page")
    url: str = Field(default="", description="URL of the source")
    snippet: str = Field(default="", description="Relevant text snippet from the source")
    relevance: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Relevance score (0.0-1.0)",
    )


class XPost(BaseModel):
    """An X/Twitter post retrieved via xAI Grok search.

    Attributes:
        text: Full text of the post.
        timestamp: When the post was created (if available).
        metrics: Engagement metrics (likes, reposts, etc.) if available.
    """

    text: str = Field(description="Full text of the post")
    timestamp: str | None = Field(
        default=None,
        description="When the post was created (ISO format or descriptive)",
    )
    metrics: dict[str, Any] | None = Field(
        default=None,
        description="Engagement metrics (likes, reposts, views, etc.)",
    )


class GroundingProfile(BaseModel):
    """Structured grounding data for a single entity.

    Produced by the EntityGroundingAgent after web search enrichment.
    Stores biographical, appearance, and affiliation data grounded
    in real-world sources rather than LLM hallucinations.

    Attributes:
        entity_name: The entity's display name.
        entity_id: Clockchain figure ID (if resolved).
        grounding_model: Model used for grounding (e.g. "perplexity/sonar").
        grounded_at: Timestamp of grounding.
        biography_summary: LLM-synthesized biography from search results.
        appearance_description: Physical description from search.
        known_affiliations: Organizations, roles, and associations.
        recent_activity_summary: Summary of recent public activity.
        source_citations: List of source URLs backing the grounding.
        confidence: Overall grounding confidence (0.0-1.0).
    """

    entity_name: str = Field(description="The entity's display name")
    entity_id: str | None = Field(
        default=None,
        description="Clockchain figure ID (if resolved)",
    )
    grounding_model: str = Field(
        default="perplexity/sonar",
        description="Model used for grounding",
    )
    grounded_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp of grounding",
    )
    biography_summary: str = Field(
        default="",
        description="LLM-synthesized biography from search results",
    )
    appearance_description: str = Field(
        default="",
        description="Physical description from search",
    )
    known_affiliations: list[str] = Field(
        default_factory=list,
        description="Organizations, roles, and associations",
    )
    recent_activity_summary: str = Field(
        default="",
        description="Summary of recent public activity",
    )
    source_citations: list[str] = Field(
        default_factory=list,
        description="List of source URLs backing the grounding",
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Overall grounding confidence (0.0-1.0)",
    )
