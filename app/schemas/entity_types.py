"""Entity types for Clockchain figure resolution.

Rich data types for entity grounding, returned by resolve_figures_with_data()
and fetch_figures_by_ids().

Examples:
    >>> from app.schemas.entity_types import FigureData
    >>> fig = FigureData(
    ...     id="fig_abc123",
    ...     display_name="Julius Caesar",
    ...     entity_type="person",
    ...     grounding_status="grounded",
    ... )

Tests:
    - tests/unit/test_entity_types.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class FigureData:
    """Rich figure data from Clockchain entity resolution.

    Attributes:
        id: Clockchain figure ID.
        display_name: Canonical display name.
        aliases: Alternative names for this entity.
        entity_type: Entity type (person, organization, place, etc.).
        grounding_status: Grounding state (ungrounded, grounded, failed, skipped).
        grounded_at: UTC timestamp of last grounding.
        grounding_confidence: Confidence score 0.0-1.0.
        external_ids: External identifiers including grounding_sources.
        wikidata_qid: Wikidata QID if available.
    """

    id: str
    display_name: str
    aliases: list[str] = field(default_factory=list)
    entity_type: str = "person"
    grounding_status: str = "ungrounded"
    grounded_at: datetime | None = None
    grounding_confidence: float | None = None
    external_ids: dict = field(default_factory=dict)
    wikidata_qid: str | None = None

    @property
    def is_grounded(self) -> bool:
        """Check if this figure has been grounded."""
        return self.grounding_status == "grounded"

    @property
    def grounding_sources(self) -> list[str]:
        """Extract grounding source URLs from external_ids."""
        return self.external_ids.get("grounding_sources", [])

    @classmethod
    def from_api_response(cls, figure: dict) -> FigureData:
        """Parse a figure dict from the Clockchain API response.

        Args:
            figure: Dict from the API response (resolve/batch or GET /figures/{id}).

        Returns:
            Populated FigureData instance.
        """
        external_ids = figure.get("external_ids") or {}
        wikidata_qid = external_ids.get("wikidata_qid") or figure.get("wikidata_qid")

        grounded_at_raw = figure.get("grounded_at")
        grounded_at = None
        if grounded_at_raw:
            try:
                grounded_at = datetime.fromisoformat(
                    grounded_at_raw.replace("Z", "+00:00")
                )
            except (ValueError, AttributeError):
                pass

        return cls(
            id=figure.get("id", ""),
            display_name=figure.get("display_name", ""),
            aliases=figure.get("aliases") or [],
            entity_type=figure.get("entity_type", "person"),
            grounding_status=figure.get("grounding_status", "ungrounded"),
            grounded_at=grounded_at,
            grounding_confidence=figure.get("grounding_confidence"),
            external_ids=external_ids,
            wikidata_qid=wikidata_qid,
        )
