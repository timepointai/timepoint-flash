"""Tests for temporal system.

Tests:
    - TemporalPoint creation and validation
    - TimeUnit enum
    - Time stepping (forward/backward)
    - BCE date handling
    - TemporalNavigator
"""

import pytest

from app.core.temporal import (
    Season,
    TemporalNavigator,
    TemporalPoint,
    TimeOfDay,
    TimeUnit,
)


# TemporalPoint Tests


@pytest.mark.fast
class TestTemporalPointCreation:
    """Tests for TemporalPoint creation and validation."""

    def test_create_basic_temporal_point(self):
        """Test creating a basic temporal point with year only."""
        tp = TemporalPoint(year=1776)
        assert tp.year == 1776
        assert tp.month is None
        assert tp.day is None
        assert tp.precision == "year"

    def test_create_full_temporal_point(self):
        """Test creating a fully specified temporal point."""
        tp = TemporalPoint(
            year=1776,
            month=7,
            day=4,
            hour=14,
            season="summer",
            time_of_day="afternoon",
            era="American Revolution",
        )
        assert tp.year == 1776
        assert tp.month == 7
        assert tp.day == 4
        assert tp.hour == 14
        assert tp.season == "summer"
        assert tp.time_of_day == "afternoon"
        assert tp.era == "American Revolution"
        assert tp.precision == "hour"

    def test_create_bce_temporal_point(self):
        """Test creating a BCE temporal point."""
        tp = TemporalPoint(year=-44, month=3, day=15)
        assert tp.year == -44
        assert tp.is_bce is True
        assert tp.display_year == "44 BCE"

    def test_ce_display_year(self):
        """Test CE display year format."""
        tp = TemporalPoint(year=1776)
        assert tp.is_bce is False
        assert tp.display_year == "1776 CE"

    def test_season_validation_valid(self):
        """Test valid season values."""
        for season in ["spring", "summer", "fall", "winter"]:
            tp = TemporalPoint(year=2000, season=season)
            assert tp.season == season

    def test_season_validation_autumn_normalized(self):
        """Test that 'autumn' is normalized to 'fall'."""
        tp = TemporalPoint(year=2000, season="autumn")
        assert tp.season == "fall"

    def test_season_validation_invalid(self):
        """Test invalid season raises error."""
        with pytest.raises(ValueError):
            TemporalPoint(year=2000, season="invalid")

    def test_precision_levels(self):
        """Test different precision levels."""
        assert TemporalPoint(year=2000).precision == "year"
        assert TemporalPoint(year=2000, month=6).precision == "month"
        assert TemporalPoint(year=2000, month=6, day=15).precision == "day"
        assert TemporalPoint(year=2000, month=6, day=15, hour=12).precision == "hour"
        assert TemporalPoint(year=2000, month=6, day=15, hour=12, minute=30).precision == "minute"
        assert TemporalPoint(year=2000, month=6, day=15, hour=12, minute=30, second=45).precision == "second"


@pytest.mark.fast
class TestTemporalPointStep:
    """Tests for TemporalPoint time stepping."""

    def test_step_forward_day(self):
        """Test stepping forward by one day."""
        tp = TemporalPoint(year=1776, month=7, day=4)
        next_day = tp.step(1, TimeUnit.DAY)
        assert next_day.day == 5
        assert next_day.month == 7
        assert next_day.year == 1776

    def test_step_backward_day(self):
        """Test stepping backward by one day."""
        tp = TemporalPoint(year=1776, month=7, day=4)
        prev_day = tp.step(-1, TimeUnit.DAY)
        assert prev_day.day == 3

    def test_step_forward_week(self):
        """Test stepping forward by one week."""
        tp = TemporalPoint(year=1776, month=7, day=4)
        next_week = tp.step(1, TimeUnit.WEEK)
        assert next_week.day == 11

    def test_step_forward_month(self):
        """Test stepping forward by one month."""
        tp = TemporalPoint(year=1776, month=7)
        next_month = tp.step(1, TimeUnit.MONTH)
        assert next_month.month == 8
        assert next_month.year == 1776

    def test_step_forward_month_year_rollover(self):
        """Test stepping forward month with year rollover."""
        tp = TemporalPoint(year=1776, month=12)
        next_month = tp.step(1, TimeUnit.MONTH)
        assert next_month.month == 1
        assert next_month.year == 1777

    def test_step_forward_year(self):
        """Test stepping forward by year."""
        tp = TemporalPoint(year=1776)
        next_year = tp.step(1, TimeUnit.YEAR)
        assert next_year.year == 1777

    def test_step_backward_year(self):
        """Test stepping backward by year."""
        tp = TemporalPoint(year=1776)
        prev_year = tp.step(-1, TimeUnit.YEAR)
        assert prev_year.year == 1775

    def test_step_bce_forward(self):
        """Test stepping forward in BCE."""
        tp = TemporalPoint(year=-50)
        next_year = tp.step(1, TimeUnit.YEAR)
        assert next_year.year == -49

    def test_step_bce_backward(self):
        """Test stepping backward in BCE."""
        tp = TemporalPoint(year=-50)
        prev_year = tp.step(-1, TimeUnit.YEAR)
        assert prev_year.year == -51

    def test_step_preserves_era(self):
        """Test that stepping preserves era."""
        tp = TemporalPoint(year=1776, era="American Revolution")
        next_year = tp.step(1, TimeUnit.YEAR)
        assert next_year.era == "American Revolution"


@pytest.mark.fast
class TestTemporalPointConversion:
    """Tests for TemporalPoint conversion methods."""

    def test_to_dict(self):
        """Test converting to dictionary."""
        tp = TemporalPoint(year=1776, month=7, day=4, season="summer")
        d = tp.to_dict()
        assert d["year"] == 1776
        assert d["month"] == 7
        assert d["day"] == 4
        assert d["season"] == "summer"
        assert d["display_year"] == "1776 CE"
        assert d["is_bce"] is False

    def test_str_representation(self):
        """Test string representation."""
        tp = TemporalPoint(year=1776, month=7, day=4, time_of_day="afternoon")
        s = str(tp)
        assert "1776 CE" in s
        assert "July" in s
        assert "4" in s
        assert "afternoon" in s

    def test_from_datetime(self):
        """Test creating from Python datetime."""
        from datetime import datetime

        dt = datetime(1776, 7, 4, 14, 30, 0)
        tp = TemporalPoint.from_datetime(dt, era="American Revolution")
        assert tp.year == 1776
        assert tp.month == 7
        assert tp.day == 4
        assert tp.hour == 14
        assert tp.minute == 30
        assert tp.era == "American Revolution"
        assert tp.season == "summer"


# TimeUnit Tests


@pytest.mark.fast
class TestTimeUnit:
    """Tests for TimeUnit enum."""

    def test_time_unit_values(self):
        """Test TimeUnit enum values."""
        assert TimeUnit.SECOND.value == "second"
        assert TimeUnit.MINUTE.value == "minute"
        assert TimeUnit.HOUR.value == "hour"
        assert TimeUnit.DAY.value == "day"
        assert TimeUnit.WEEK.value == "week"
        assert TimeUnit.MONTH.value == "month"
        assert TimeUnit.YEAR.value == "year"


# TemporalNavigator Tests


@pytest.mark.fast
class TestTemporalNavigator:
    """Tests for TemporalNavigator."""

    def test_next_moment(self):
        """Test getting next moment."""
        nav = TemporalNavigator()
        current = TemporalPoint(year=1776, month=7, day=4)
        next_tp = nav.next_moment(current, 1, TimeUnit.DAY)
        assert next_tp.day == 5

    def test_prior_moment(self):
        """Test getting prior moment."""
        nav = TemporalNavigator()
        current = TemporalPoint(year=1776, month=7, day=4)
        prior_tp = nav.prior_moment(current, 1, TimeUnit.DAY)
        assert prior_tp.day == 3

    def test_generate_sequence_forward(self):
        """Test generating a forward sequence."""
        nav = TemporalNavigator()
        start = TemporalPoint(year=1776, month=7, day=1)
        sequence = nav.generate_sequence(start, 5, TimeUnit.DAY, direction=1)

        assert len(sequence) == 5
        assert sequence[0].day == 1
        assert sequence[1].day == 2
        assert sequence[2].day == 3
        assert sequence[3].day == 4
        assert sequence[4].day == 5

    def test_generate_sequence_backward(self):
        """Test generating a backward sequence."""
        nav = TemporalNavigator()
        start = TemporalPoint(year=1776, month=7, day=10)
        sequence = nav.generate_sequence(start, 3, TimeUnit.DAY, direction=-1)

        assert len(sequence) == 3
        assert sequence[0].day == 10
        assert sequence[1].day == 9
        assert sequence[2].day == 8

    def test_infer_season(self):
        """Test season inference from month."""
        assert TemporalNavigator.infer_season(1, 2000) == "winter"
        assert TemporalNavigator.infer_season(4, 2000) == "spring"
        assert TemporalNavigator.infer_season(7, 2000) == "summer"
        assert TemporalNavigator.infer_season(10, 2000) == "fall"
        assert TemporalNavigator.infer_season(None, 2000) is None

    def test_infer_era(self):
        """Test era inference from year."""
        assert "Ancient" in TemporalNavigator.infer_era(-4000)
        assert TemporalNavigator.infer_era(500) == "Classical Antiquity"
        assert TemporalNavigator.infer_era(1000) == "Medieval"
        assert TemporalNavigator.infer_era(1600) == "Early Modern"
        assert TemporalNavigator.infer_era(1850) == "19th Century"
        assert TemporalNavigator.infer_era(1950) == "20th Century"
        assert TemporalNavigator.infer_era(2020) == "Contemporary"


# Season and TimeOfDay Enum Tests


@pytest.mark.fast
class TestEnums:
    """Tests for Season and TimeOfDay enums."""

    def test_season_values(self):
        """Test Season enum values."""
        assert Season.SPRING.value == "spring"
        assert Season.SUMMER.value == "summer"
        assert Season.FALL.value == "fall"
        assert Season.WINTER.value == "winter"

    def test_time_of_day_values(self):
        """Test TimeOfDay enum values."""
        assert TimeOfDay.DAWN.value == "dawn"
        assert TimeOfDay.MORNING.value == "morning"
        assert TimeOfDay.MIDDAY.value == "midday"
        assert TimeOfDay.AFTERNOON.value == "afternoon"
        assert TimeOfDay.EVENING.value == "evening"
        assert TimeOfDay.DUSK.value == "dusk"
        assert TimeOfDay.NIGHT.value == "night"
        assert TimeOfDay.MIDNIGHT.value == "midnight"
