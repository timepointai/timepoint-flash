"""Timeline step schema for temporal extraction.

The Timeline step extracts precise temporal coordinates from the query,
including year, month, day, season, location, and historical era.

Examples:
    >>> from app.schemas.timeline import TimelineData
    >>> data = TimelineData(
    ...     year=1776,
    ...     month=7,
    ...     day=4,
    ...     season="summer",
    ...     location="Independence Hall, Philadelphia",
    ...     era="American Revolution"
    ... )

Tests:
    - tests/unit/test_schemas.py::test_timeline_data_valid
    - tests/unit/test_schemas.py::test_timeline_data_bce
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class TimelineData(BaseModel):
    """Temporal coordinates extracted from the query.

    Attributes:
        year: The year (negative for BCE)
        month: Month (1-12), optional
        day: Day of month (1-31), optional
        hour: Hour (0-23), optional
        season: Season name
        time_of_day: Descriptive time period
        location: Geographic location
        era: Historical era name
        historical_context: Brief context about the period
        is_approximate: Whether the date is approximate

    Examples:
        >>> data = TimelineData(year=-44, month=3, day=15)
        >>> data.display_year
        '44 BCE'
    """

    # Temporal fields
    year: int = Field(..., description="Year (negative for BCE)")
    month: int | None = Field(default=None, ge=1, le=12)
    day: int | None = Field(default=None, ge=1, le=31)
    hour: int | None = Field(default=None, ge=0, le=23)

    # Contextual fields
    season: str | None = Field(
        default=None,
        description="Season (spring, summer, fall, winter)",
    )
    time_of_day: str | None = Field(
        default=None,
        description="Time description (morning, afternoon, evening, night)",
    )
    location: str = Field(
        ...,
        description="Geographic location",
    )
    era: str | None = Field(
        default=None,
        description="Historical era name",
    )

    # Additional context
    historical_context: str | None = Field(
        default=None,
        description="Brief context about this time period",
    )
    is_approximate: bool = Field(
        default=False,
        description="Whether the date is approximate",
    )
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Confidence in the temporal extraction",
    )

    @field_validator("season")
    @classmethod
    def validate_season(cls, v: str | None) -> str | None:
        """Normalize season value."""
        if v is None:
            return None
        v_lower = v.lower()
        if v_lower == "autumn":
            return "fall"
        if v_lower not in {"spring", "summer", "fall", "winter"}:
            return None
        return v_lower

    @property
    def display_year(self) -> str:
        """Get human-readable year string."""
        if self.year < 0:
            return f"{abs(self.year)} BCE"
        return f"{self.year} CE"

    @property
    def is_bce(self) -> bool:
        """Check if this is a BCE date."""
        return self.year < 0

    def to_temporal_dict(self) -> dict:
        """Convert to dictionary for Timepoint model."""
        return {
            "year": self.year,
            "month": self.month,
            "day": self.day,
            "season": self.season,
            "time_of_day": self.time_of_day,
            "location": self.location,
            "era": self.era,
        }
