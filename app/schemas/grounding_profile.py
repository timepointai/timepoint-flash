"""Grounding profile schema for entity-grounded character generation.

Holds structured real-world data for a named entity, produced by the
grounding pipeline and consumed by CharacterBioAgent to enrich prompts.

Examples:
    >>> from app.schemas.grounding_profile import GroundingProfile
    >>> profile = GroundingProfile(
    ...     entity_name="Marc Andreessen",
    ...     grounding_model="perplexity/sonar",
    ...     grounded_at=datetime.utcnow(),
    ...     biography_summary="Co-founder of Netscape and a16z...",
    ...     appearance_description="Tall, shaved head, often in casual attire.",
    ...     known_affiliations=["Andreessen Horowitz", "Netscape"],
    ...     source_citations=["https://a16z.com/team/marc-andreessen/"],
    ...     confidence=0.92,
    ... )
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class GroundingProfile(BaseModel):
    """Structured real-world profile for a named entity.

    Produced by the grounding agent and injected into CharacterBioAgent
    prompts so that generated bios reflect documented facts rather than
    LLM hallucinations.

    Attributes:
        entity_name: Display name of the entity (person, org, place)
        entity_id: Optional Clockchain figure ID
        grounding_model: OpenRouter model ID used to produce this profile
        grounded_at: UTC timestamp when grounding was performed
        biography_summary: Concise factual biography
        appearance_description: Documented or well-known physical description
        known_affiliations: Organisations, groups, or roles the entity is associated with
        source_citations: URLs or references supporting the grounded data
        confidence: Float in [0, 1] reflecting grounding confidence
    """

    entity_name: str = Field(..., description="Display name of the entity")
    entity_id: str | None = Field(
        default=None,
        description="Clockchain figure ID for entity persistence",
    )
    grounding_model: str = Field(
        ...,
        description="OpenRouter model ID used for grounding (e.g. perplexity/sonar)",
    )
    grounded_at: datetime = Field(
        ...,
        description="UTC timestamp when grounding was performed",
    )
    biography_summary: str = Field(
        ...,
        description="Concise factual biography based on grounded sources",
    )
    appearance_description: str = Field(
        default="",
        description="Documented or well-known physical description",
    )
    known_affiliations: list[str] = Field(
        default_factory=list,
        description="Organisations, groups, or roles the entity is associated with",
    )
    source_citations: list[str] = Field(
        default_factory=list,
        description="URLs or references supporting the grounded data",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Grounding confidence score between 0 and 1",
    )
