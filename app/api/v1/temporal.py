"""Temporal navigation API endpoints.

Provides endpoints for navigating through time from existing timepoints.

Endpoints:
    POST /api/v1/temporal/{id}/next - Generate next moment
    POST /api/v1/temporal/{id}/prior - Generate prior moment

Examples:
    >>> # Generate next day
    >>> POST /api/v1/temporal/{id}/next
    >>> {"units": 1, "unit": "day"}

Tests:
    - tests/unit/test_api_temporal.py::test_next_moment
    - tests/unit/test_api_temporal.py::test_prior_moment
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pipeline import GenerationPipeline
from app.core.temporal import TemporalNavigator, TemporalPoint, TimeUnit
from app.database import get_db_session
from app.models import Timepoint, TimepointStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/temporal", tags=["temporal"])


# Request/Response Models


class NavigationRequest(BaseModel):
    """Request to navigate in time.

    Attributes:
        units: Number of time units to move
        unit: Time unit (day, week, month, year)
    """

    units: int = Field(
        default=1,
        ge=1,
        le=365,
        description="Number of time units to step",
    )
    unit: str = Field(
        default="day",
        description="Time unit (day, week, month, year)",
    )


class NavigationResponse(BaseModel):
    """Response from temporal navigation."""

    source_id: str
    target_id: str
    source_year: int | None
    target_year: int | None
    direction: str
    units: int
    unit: str
    message: str


# Helper Functions


def get_time_unit(unit: str) -> TimeUnit:
    """Convert string to TimeUnit enum."""
    unit_map = {
        "second": TimeUnit.SECOND,
        "minute": TimeUnit.MINUTE,
        "hour": TimeUnit.HOUR,
        "day": TimeUnit.DAY,
        "week": TimeUnit.WEEK,
        "month": TimeUnit.MONTH,
        "year": TimeUnit.YEAR,
    }
    return unit_map.get(unit.lower(), TimeUnit.DAY)


def timepoint_to_temporal_point(tp: Timepoint) -> TemporalPoint:
    """Convert Timepoint to TemporalPoint for navigation."""
    return TemporalPoint(
        year=tp.year or 2000,  # Default year if not set
        month=tp.month,
        day=tp.day,
        season=tp.season,
        time_of_day=tp.time_of_day,
        era=tp.era,
    )


async def generate_moment_from_context(
    source_tp: Timepoint,
    target_point: TemporalPoint,
    direction: str,
    session: AsyncSession,
) -> Timepoint:
    """Generate a new timepoint based on temporal navigation.

    Args:
        source_tp: Source timepoint with context
        target_point: Target temporal coordinates
        direction: 'next' or 'prior'
        session: Database session

    Returns:
        New generated Timepoint
    """
    # Build context-aware query
    if direction == "next":
        query = f"The same scene at {source_tp.location}, {abs(target_point.year)} {'BCE' if target_point.year < 0 else 'CE'}, continuing from the previous moment"
    else:
        query = f"The scene at {source_tp.location}, {abs(target_point.year)} {'BCE' if target_point.year < 0 else 'CE'}, moments before the next scene"

    # Run pipeline
    pipeline = GenerationPipeline()
    state = await pipeline.run(query)

    # Create timepoint
    new_tp = pipeline.state_to_timepoint(state)

    # Link to source
    new_tp.parent_id = source_tp.id if direction == "next" else None

    # Override with calculated temporal data
    new_tp.year = target_point.year
    new_tp.month = target_point.month
    new_tp.day = target_point.day
    new_tp.season = target_point.season or source_tp.season
    new_tp.time_of_day = source_tp.time_of_day  # Preserve time of day

    # Save to database
    session.add(new_tp)
    await session.commit()
    await session.refresh(new_tp)

    return new_tp


# Endpoints


@router.post("/{timepoint_id}/next", response_model=NavigationResponse)
async def generate_next_moment(
    timepoint_id: str,
    request: NavigationRequest,
    session: AsyncSession = Depends(get_db_session),
) -> NavigationResponse:
    """Generate the next temporal moment from a timepoint.

    Steps forward in time from the source timepoint,
    preserving character and scene context.

    Args:
        timepoint_id: Source timepoint UUID
        request: Navigation parameters
        session: Database session

    Returns:
        NavigationResponse with new timepoint info

    Raises:
        HTTPException: If source timepoint not found
    """
    logger.info(f"Next moment request: {timepoint_id}, {request.units} {request.unit}")

    # Get source timepoint
    result = await session.execute(
        select(Timepoint).where(Timepoint.id == timepoint_id)
    )
    source_tp = result.scalar_one_or_none()

    if not source_tp:
        raise HTTPException(status_code=404, detail="Source timepoint not found")

    if not source_tp.is_complete:
        raise HTTPException(
            status_code=400,
            detail="Source timepoint must be completed before navigation",
        )

    # Calculate target temporal point
    source_point = timepoint_to_temporal_point(source_tp)
    time_unit = get_time_unit(request.unit)
    target_point = source_point.step(request.units, time_unit)

    # Generate new moment
    new_tp = await generate_moment_from_context(
        source_tp=source_tp,
        target_point=target_point,
        direction="next",
        session=session,
    )

    return NavigationResponse(
        source_id=source_tp.id,
        target_id=new_tp.id,
        source_year=source_tp.year,
        target_year=new_tp.year,
        direction="next",
        units=request.units,
        unit=request.unit,
        message=f"Generated moment {request.units} {request.unit}(s) forward",
    )


@router.post("/{timepoint_id}/prior", response_model=NavigationResponse)
async def generate_prior_moment(
    timepoint_id: str,
    request: NavigationRequest,
    session: AsyncSession = Depends(get_db_session),
) -> NavigationResponse:
    """Generate the prior temporal moment from a timepoint.

    Steps backward in time from the source timepoint,
    preserving character and scene context.

    Args:
        timepoint_id: Source timepoint UUID
        request: Navigation parameters
        session: Database session

    Returns:
        NavigationResponse with new timepoint info

    Raises:
        HTTPException: If source timepoint not found
    """
    logger.info(f"Prior moment request: {timepoint_id}, {request.units} {request.unit}")

    # Get source timepoint
    result = await session.execute(
        select(Timepoint).where(Timepoint.id == timepoint_id)
    )
    source_tp = result.scalar_one_or_none()

    if not source_tp:
        raise HTTPException(status_code=404, detail="Source timepoint not found")

    if not source_tp.is_complete:
        raise HTTPException(
            status_code=400,
            detail="Source timepoint must be completed before navigation",
        )

    # Calculate target temporal point (negative step)
    source_point = timepoint_to_temporal_point(source_tp)
    time_unit = get_time_unit(request.unit)
    target_point = source_point.step(-request.units, time_unit)

    # Generate new moment
    new_tp = await generate_moment_from_context(
        source_tp=source_tp,
        target_point=target_point,
        direction="prior",
        session=session,
    )

    # For prior, the new timepoint should be the parent
    source_tp.parent_id = new_tp.id
    await session.commit()

    return NavigationResponse(
        source_id=source_tp.id,
        target_id=new_tp.id,
        source_year=source_tp.year,
        target_year=new_tp.year,
        direction="prior",
        units=request.units,
        unit=request.unit,
        message=f"Generated moment {request.units} {request.unit}(s) backward",
    )


@router.get("/{timepoint_id}/sequence")
async def get_temporal_sequence(
    timepoint_id: str,
    direction: str = Query("both", description="Sequence direction: prior, next, or both"),
    limit: int = Query(10, ge=1, le=50, description="Maximum timepoints to return"),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Get the temporal sequence for a timepoint.

    Returns linked prior and/or next timepoints in the sequence.

    Args:
        timepoint_id: Center timepoint UUID
        direction: Which direction to fetch
        limit: Maximum results per direction
        session: Database session

    Returns:
        Dictionary with prior and next timepoint lists
    """
    # Get center timepoint
    result = await session.execute(
        select(Timepoint).where(Timepoint.id == timepoint_id)
    )
    center_tp = result.scalar_one_or_none()

    if not center_tp:
        raise HTTPException(status_code=404, detail="Timepoint not found")

    response: dict[str, Any] = {
        "center": {
            "id": center_tp.id,
            "year": center_tp.year,
            "slug": center_tp.slug,
        },
        "prior": [],
        "next": [],
    }

    # Get prior chain
    if direction in ("prior", "both"):
        current = center_tp
        for _ in range(limit):
            if current.parent_id:
                result = await session.execute(
                    select(Timepoint).where(Timepoint.id == current.parent_id)
                )
                parent = result.scalar_one_or_none()
                if parent:
                    response["prior"].append({
                        "id": parent.id,
                        "year": parent.year,
                        "slug": parent.slug,
                    })
                    current = parent
                else:
                    break
            else:
                break

    # Get next chain (children)
    if direction in ("next", "both"):
        current_id = center_tp.id
        for _ in range(limit):
            result = await session.execute(
                select(Timepoint).where(Timepoint.parent_id == current_id)
            )
            child = result.scalar_one_or_none()
            if child:
                response["next"].append({
                    "id": child.id,
                    "year": child.year,
                    "slug": child.slug,
                })
                current_id = child.id
            else:
                break

    return response
