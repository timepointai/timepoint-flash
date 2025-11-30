"""Synthetic time system for temporal navigation.

This module provides the temporal coordinate system for representing
and navigating through historical time periods.

Supports:
- BCE/CE dates (negative years for BCE)
- Approximate dates (year only, year+month, full date)
- Time stepping (forward/backward by units)
- Seasonal and time-of-day metadata

Examples:
    >>> from app.core.temporal import TemporalPoint, TimeUnit
    >>> tp = TemporalPoint(year=1776, month=7, day=4, season="summer")
    >>> next_day = tp.step(1, TimeUnit.DAY)
    >>> next_day.day
    5

    >>> # BCE dates use negative years
    >>> rome = TemporalPoint(year=-50, season="fall", era="Roman Republic")
    >>> rome.is_bce
    True

Tests:
    - tests/unit/test_temporal.py::test_temporal_point_creation
    - tests/unit/test_temporal.py::test_temporal_point_step
    - tests/unit/test_temporal.py::test_temporal_point_bce
    - tests/unit/test_temporal.py::test_temporal_navigator
"""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class TimeUnit(str, Enum):
    """Units of time for stepping through temporal points.

    Examples:
        >>> TimeUnit.DAY.value
        'day'
    """

    SECOND = "second"
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"


class Season(str, Enum):
    """Seasonal periods.

    Note: Season mapping depends on hemisphere, but we use
    Northern Hemisphere conventions for historical events.
    """

    SPRING = "spring"
    SUMMER = "summer"
    FALL = "fall"
    WINTER = "winter"


class TimeOfDay(str, Enum):
    """Time of day periods."""

    DAWN = "dawn"
    MORNING = "morning"
    MIDDAY = "midday"
    AFTERNOON = "afternoon"
    EVENING = "evening"
    DUSK = "dusk"
    NIGHT = "night"
    MIDNIGHT = "midnight"


class TemporalPoint(BaseModel):
    """A point in synthetic time.

    Represents a temporal coordinate with varying precision.
    Supports BCE dates via negative years.

    Attributes:
        year: The year (negative for BCE)
        month: Month (1-12), optional
        day: Day of month (1-31), optional
        hour: Hour (0-23), optional
        minute: Minute (0-59), optional
        second: Second (0-59), optional
        season: Season name (spring, summer, fall, winter)
        time_of_day: Descriptive time (morning, afternoon, etc.)
        era: Historical era name (e.g., "Roman Republic", "Renaissance")

    Examples:
        >>> tp = TemporalPoint(year=1776, month=7, day=4)
        >>> tp.display_year
        '1776 CE'

        >>> bce = TemporalPoint(year=-44, month=3, day=15)
        >>> bce.display_year
        '44 BCE'
    """

    year: int = Field(..., description="Year (negative for BCE)")
    month: int | None = Field(default=None, ge=1, le=12)
    day: int | None = Field(default=None, ge=1, le=31)
    hour: int | None = Field(default=None, ge=0, le=23)
    minute: int | None = Field(default=None, ge=0, le=59)
    second: int | None = Field(default=None, ge=0, le=59)

    # Metadata
    season: str | None = Field(default=None)
    time_of_day: str | None = Field(default=None)
    era: str | None = Field(default=None)

    @field_validator("season")
    @classmethod
    def validate_season(cls, v: str | None) -> str | None:
        """Validate season value."""
        if v is None:
            return None
        valid = {"spring", "summer", "fall", "autumn", "winter"}
        if v.lower() not in valid:
            raise ValueError(f"Invalid season: {v}. Must be one of {valid}")
        # Normalize autumn to fall
        return "fall" if v.lower() == "autumn" else v.lower()

    @property
    def is_bce(self) -> bool:
        """Check if this is a BCE date."""
        return self.year < 0

    @property
    def display_year(self) -> str:
        """Get human-readable year string.

        Examples:
            >>> TemporalPoint(year=1776).display_year
            '1776 CE'
            >>> TemporalPoint(year=-44).display_year
            '44 BCE'
        """
        if self.is_bce:
            return f"{abs(self.year)} BCE"
        return f"{self.year} CE"

    @property
    def precision(self) -> str:
        """Get the precision level of this temporal point.

        Returns:
            'second', 'minute', 'hour', 'day', 'month', or 'year'
        """
        if self.second is not None:
            return "second"
        if self.minute is not None:
            return "minute"
        if self.hour is not None:
            return "hour"
        if self.day is not None:
            return "day"
        if self.month is not None:
            return "month"
        return "year"

    def to_datetime(self) -> datetime:
        """Convert to Python datetime (best effort).

        Note:
            BCE dates are mapped to year 1 (datetime doesn't support BCE).
            This is only useful for relative calculations.

        Returns:
            datetime object (approximate for BCE dates)
        """
        # Handle BCE by using a proxy year
        year = max(1, self.year) if self.year > 0 else 1

        return datetime(
            year=year,
            month=self.month or 1,
            day=self.day or 1,
            hour=self.hour or 0,
            minute=self.minute or 0,
            second=self.second or 0,
        )

    @classmethod
    def from_datetime(cls, dt: datetime, era: str | None = None) -> TemporalPoint:
        """Create from Python datetime.

        Args:
            dt: Python datetime object
            era: Optional era name

        Returns:
            New TemporalPoint
        """
        # Infer season from month (Northern Hemisphere)
        month_to_season = {
            12: "winter", 1: "winter", 2: "winter",
            3: "spring", 4: "spring", 5: "spring",
            6: "summer", 7: "summer", 8: "summer",
            9: "fall", 10: "fall", 11: "fall",
        }

        # Infer time of day from hour
        hour_to_time = {
            range(5, 7): "dawn",
            range(7, 12): "morning",
            range(12, 13): "midday",
            range(13, 17): "afternoon",
            range(17, 19): "evening",
            range(19, 21): "dusk",
            range(21, 24): "night",
            range(0, 5): "night",
        }

        time_of_day = "day"
        for hours, name in hour_to_time.items():
            if dt.hour in hours:
                time_of_day = name
                break

        return cls(
            year=dt.year,
            month=dt.month,
            day=dt.day,
            hour=dt.hour,
            minute=dt.minute,
            second=dt.second,
            season=month_to_season.get(dt.month),
            time_of_day=time_of_day,
            era=era,
        )

    def step(self, units: int, unit: TimeUnit) -> TemporalPoint:
        """Step forward or backward in time.

        Args:
            units: Number of units to step (negative for backward)
            unit: The time unit to step by

        Returns:
            New TemporalPoint at the new time

        Examples:
            >>> tp = TemporalPoint(year=1776, month=7, day=4)
            >>> next_week = tp.step(1, TimeUnit.WEEK)
            >>> next_week.day
            11

            >>> # BCE dates work correctly
            >>> bce = TemporalPoint(year=-50)
            >>> earlier = bce.step(-10, TimeUnit.YEAR)
            >>> earlier.year
            -60
        """
        # For year-only precision, just adjust year
        if unit == TimeUnit.YEAR:
            new_year = self.year + units
            return self.model_copy(update={"year": new_year})

        # For month precision with month unit
        if unit == TimeUnit.MONTH:
            # Calculate total months
            current_month = (self.month or 1) - 1  # 0-indexed
            total_months = self.year * 12 + current_month + units

            new_year = total_months // 12
            new_month = (total_months % 12) + 1  # Back to 1-indexed

            # Handle negative months
            if new_month <= 0:
                new_year -= 1
                new_month += 12

            return self.model_copy(update={"year": new_year, "month": new_month})

        # For smaller units, use timedelta
        delta_map = {
            TimeUnit.SECOND: timedelta(seconds=units),
            TimeUnit.MINUTE: timedelta(minutes=units),
            TimeUnit.HOUR: timedelta(hours=units),
            TimeUnit.DAY: timedelta(days=units),
            TimeUnit.WEEK: timedelta(weeks=units),
        }

        if unit not in delta_map:
            raise ValueError(f"Unsupported time unit: {unit}")

        # Convert to datetime, apply delta, convert back
        # For BCE, we need to handle year offset
        year_offset = 0
        if self.is_bce:
            year_offset = self.year - 1  # How much to adjust
            base_dt = datetime(
                year=1,
                month=self.month or 1,
                day=self.day or 1,
                hour=self.hour or 0,
                minute=self.minute or 0,
                second=self.second or 0,
            )
        else:
            base_dt = self.to_datetime()

        new_dt = base_dt + delta_map[unit]

        # Create new point
        new_point = TemporalPoint.from_datetime(new_dt, era=self.era)

        # Adjust year for BCE
        if self.is_bce:
            new_point = new_point.model_copy(
                update={"year": new_point.year + year_offset}
            )

        return new_point

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "year": self.year,
            "month": self.month,
            "day": self.day,
            "hour": self.hour,
            "minute": self.minute,
            "second": self.second,
            "season": self.season,
            "time_of_day": self.time_of_day,
            "era": self.era,
            "display_year": self.display_year,
            "is_bce": self.is_bce,
            "precision": self.precision,
        }

    def __str__(self) -> str:
        """Human-readable string representation."""
        parts = [self.display_year]

        if self.month:
            month_names = [
                "", "January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December"
            ]
            parts.append(month_names[self.month])

        if self.day:
            parts.append(str(self.day))

        if self.time_of_day:
            parts.append(f"({self.time_of_day})")

        return " ".join(parts)


class TemporalNavigator:
    """Navigate through temporal points with context.

    Provides methods for generating adjacent moments in time
    while preserving narrative context.

    Examples:
        >>> nav = TemporalNavigator()
        >>> current = TemporalPoint(year=1776, month=7, day=4)
        >>> next_point = nav.next_moment(current, 1, TimeUnit.DAY)
    """

    def next_moment(
        self,
        current: TemporalPoint,
        units: int = 1,
        unit: TimeUnit = TimeUnit.DAY,
    ) -> TemporalPoint:
        """Get the next temporal moment.

        Args:
            current: Current temporal point
            units: Number of units forward
            unit: Time unit

        Returns:
            New TemporalPoint stepped forward
        """
        return current.step(units, unit)

    def prior_moment(
        self,
        current: TemporalPoint,
        units: int = 1,
        unit: TimeUnit = TimeUnit.DAY,
    ) -> TemporalPoint:
        """Get a prior temporal moment.

        Args:
            current: Current temporal point
            units: Number of units backward
            unit: Time unit

        Returns:
            New TemporalPoint stepped backward
        """
        return current.step(-units, unit)

    def generate_sequence(
        self,
        start: TemporalPoint,
        count: int,
        unit: TimeUnit = TimeUnit.DAY,
        direction: int = 1,
    ) -> list[TemporalPoint]:
        """Generate a sequence of temporal points.

        Args:
            start: Starting temporal point
            count: Number of points to generate
            unit: Time unit for each step
            direction: 1 for forward, -1 for backward

        Returns:
            List of TemporalPoints
        """
        points = [start]
        current = start

        for _ in range(count - 1):
            current = current.step(direction, unit)
            points.append(current)

        return points

    @staticmethod
    def infer_season(month: int | None, year: int) -> str | None:
        """Infer season from month (Northern Hemisphere).

        Args:
            month: Month number (1-12)
            year: Year (used for hemisphere, though we default to Northern)

        Returns:
            Season name or None
        """
        if month is None:
            return None

        season_map = {
            12: "winter", 1: "winter", 2: "winter",
            3: "spring", 4: "spring", 5: "spring",
            6: "summer", 7: "summer", 8: "summer",
            9: "fall", 10: "fall", 11: "fall",
        }
        return season_map.get(month)

    @staticmethod
    def infer_era(year: int, location: str | None = None) -> str | None:
        """Infer historical era from year and location.

        Args:
            year: The year
            location: Optional location hint

        Returns:
            Era name or None

        Note:
            This is a simplified inference. The actual era
            should come from LLM analysis of the query.
        """
        # Very rough era mapping
        if year < -3000:
            return "Ancient"
        elif year < -500:
            return "Ancient Civilizations"
        elif year <= 500:
            return "Classical Antiquity"
        elif year < 1500:
            return "Medieval"
        elif year < 1800:
            return "Early Modern"
        elif year < 1900:
            return "19th Century"
        elif year < 2000:
            return "20th Century"
        else:
            return "Contemporary"
