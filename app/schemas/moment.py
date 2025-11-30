"""Moment step schema for plot and tension.

The Moment step captures the dramatic narrative, stakes,
and emotional tension of the scene.

Examples:
    >>> from app.schemas.moment import MomentData
    >>> moment = MomentData(
    ...     plot_summary="The delegates prepare to sign...",
    ...     stakes="The future of American independence",
    ...     tension_arc="rising"
    ... )

Tests:
    - tests/unit/test_schemas.py::test_moment_data_valid
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class MomentData(BaseModel):
    """Plot and narrative tension data for the scene.

    Captures what's happening, what's at stake, and the
    emotional arc of the moment.

    Attributes:
        plot_summary: Brief summary of what's happening
        before_context: What just happened before this moment
        after_context: What happens next
        stakes: What's at risk in this moment
        tension_arc: Rising, falling, climactic, or resolved
        emotional_beats: Key emotional moments
        conflict_type: Type of conflict (internal, external, etc.)
        dramatic_irony: Any irony the viewer knows
    """

    # Narrative
    plot_summary: str = Field(
        ...,
        description="Brief summary of the moment's action",
    )
    before_context: str | None = Field(
        default=None,
        description="What happened immediately before",
    )
    after_context: str | None = Field(
        default=None,
        description="What happens next (for context)",
    )

    # Stakes
    stakes: str = Field(
        default="",
        description="What's at risk in this moment",
    )
    consequences: str | None = Field(
        default=None,
        description="Potential consequences of failure",
    )

    # Tension
    tension_arc: str = Field(
        default="rising",
        description="Tension trajectory (rising, falling, climactic, resolved)",
    )
    emotional_beats: list[str] = Field(
        default_factory=list,
        description="Key emotional moments in sequence",
    )

    # Conflict
    conflict_type: str | None = Field(
        default=None,
        description="Type of conflict (internal, interpersonal, societal, etc.)",
    )
    central_question: str | None = Field(
        default=None,
        description="The central dramatic question of the moment",
    )

    # Context
    dramatic_irony: str | None = Field(
        default=None,
        description="Irony the viewer knows but characters don't",
    )
    historical_significance: str | None = Field(
        default=None,
        description="Why this moment matters historically",
    )

    @property
    def is_climactic(self) -> bool:
        """Check if this is a climactic moment."""
        return self.tension_arc == "climactic"

    def to_narrative(self) -> str:
        """Convert to narrative description."""
        parts = [self.plot_summary]
        if self.stakes:
            parts.append(f"Stakes: {self.stakes}")
        if self.tension_arc:
            parts.append(f"Tension: {self.tension_arc}")
        return ". ".join(parts)
