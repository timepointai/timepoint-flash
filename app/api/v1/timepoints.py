"""Timepoint API endpoints.

Provides REST API for timepoint generation and retrieval.

Endpoints:
    POST /api/v1/timepoints/generate - Start timepoint generation
    GET /api/v1/timepoints/{id} - Get timepoint by ID
    GET /api/v1/timepoints/slug/{slug} - Get timepoint by slug
    GET /api/v1/timepoints - List timepoints

Examples:
    >>> # Generate a timepoint
    >>> POST /api/v1/timepoints/generate
    >>> {"query": "signing of the declaration"}
    >>>
    >>> # Response
    >>> {"id": "...", "status": "completed", "slug": "signing-of-the-declaration-1776"}

Tests:
    - tests/integration/test_api_timepoints.py::test_generate_endpoint
    - tests/integration/test_api_timepoints.py::test_get_timepoint
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pipeline import GenerationPipeline
from app.database import get_db_session
from app.models import Timepoint, TimepointStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/timepoints", tags=["timepoints"])


# Request/Response Models


class GenerateRequest(BaseModel):
    """Request to generate a timepoint.

    Attributes:
        query: The temporal query to generate
    """

    query: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="Temporal query (e.g., 'signing of the declaration')",
        examples=["signing of the declaration", "rome 50 BCE", "battle of thermopylae"],
    )


class TimepointResponse(BaseModel):
    """Response containing timepoint data.

    Attributes:
        id: Timepoint ID
        query: Original query
        slug: URL-safe slug
        status: Generation status
        year: Temporal year
        location: Geographic location
        image_url: Generated image URL (if available)
        error: Error message (if failed)
    """

    id: str
    query: str
    slug: str
    status: str
    year: int | None = None
    month: int | None = None
    day: int | None = None
    season: str | None = None
    time_of_day: str | None = None
    era: str | None = None
    location: str | None = None
    image_prompt: str | None = None
    image_url: str | None = None
    created_at: str | None = None
    error: str | None = None

    # Full data (optional, for detailed requests)
    metadata: dict[str, Any] | None = None
    characters: dict[str, Any] | None = None
    scene: dict[str, Any] | None = None
    dialog: list[dict[str, Any]] | None = None

    model_config = {"from_attributes": True}


class TimepointListResponse(BaseModel):
    """Response containing list of timepoints."""

    items: list[TimepointResponse]
    total: int
    page: int
    page_size: int


class GenerateResponse(BaseModel):
    """Response after starting generation."""

    id: str
    status: str
    message: str


# Helper Functions


def timepoint_to_response(tp: Timepoint, include_full: bool = False) -> TimepointResponse:
    """Convert Timepoint model to response.

    Args:
        tp: Timepoint model
        include_full: Whether to include full metadata

    Returns:
        TimepointResponse
    """
    response = TimepointResponse(
        id=tp.id,
        query=tp.query,
        slug=tp.slug,
        status=tp.status.value if tp.status else "unknown",
        year=tp.year,
        month=tp.month,
        day=tp.day,
        season=tp.season,
        time_of_day=tp.time_of_day,
        era=tp.era,
        location=tp.location,
        image_prompt=tp.image_prompt,
        image_url=tp.image_url,
        created_at=tp.created_at.isoformat() if tp.created_at else None,
        error=tp.error_message,
    )

    if include_full:
        response.metadata = tp.metadata_json
        response.characters = tp.character_data_json
        response.scene = tp.scene_data_json
        response.dialog = tp.dialog_json

    return response


# Background Task for Generation


async def run_generation_task(
    timepoint_id: str,
    query: str,
    session_factory,
) -> None:
    """Background task to run generation pipeline.

    Args:
        timepoint_id: ID of the timepoint to update
        query: The query to generate
        session_factory: Database session factory
    """
    from app.database import get_session

    logger.info(f"Starting background generation for {timepoint_id}")

    try:
        # Run pipeline
        pipeline = GenerationPipeline()
        state = await pipeline.run(query)

        # Convert to timepoint
        generated_tp = pipeline.state_to_timepoint(state)

        # Update in database
        async with get_session() as session:
            # Get existing timepoint
            result = await session.execute(
                select(Timepoint).where(Timepoint.id == timepoint_id)
            )
            tp = result.scalar_one_or_none()

            if tp:
                # Update fields
                tp.status = generated_tp.status
                tp.year = generated_tp.year
                tp.month = generated_tp.month
                tp.day = generated_tp.day
                tp.season = generated_tp.season
                tp.time_of_day = generated_tp.time_of_day
                tp.era = generated_tp.era
                tp.location = generated_tp.location
                tp.metadata_json = generated_tp.metadata_json
                tp.character_data_json = generated_tp.character_data_json
                tp.scene_data_json = generated_tp.scene_data_json
                tp.dialog_json = generated_tp.dialog_json
                tp.image_prompt = generated_tp.image_prompt
                tp.error_message = generated_tp.error_message

                await session.commit()
                logger.info(f"Generation complete for {timepoint_id}: {tp.status}")

    except Exception as e:
        logger.error(f"Background generation failed for {timepoint_id}: {e}")
        # Update status to failed
        async with get_session() as session:
            result = await session.execute(
                select(Timepoint).where(Timepoint.id == timepoint_id)
            )
            tp = result.scalar_one_or_none()
            if tp:
                tp.status = TimepointStatus.FAILED
                tp.error_message = str(e)
                await session.commit()


# Endpoints


@router.post("/generate", response_model=GenerateResponse)
async def generate_timepoint(
    request: GenerateRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session),
) -> GenerateResponse:
    """Start timepoint generation.

    Creates a new timepoint in PENDING status and starts
    background generation.

    Args:
        request: Generation request with query
        background_tasks: FastAPI background tasks
        session: Database session

    Returns:
        GenerateResponse with timepoint ID

    Raises:
        HTTPException: If generation cannot be started
    """
    logger.info(f"Generate request: {request.query}")

    # Create pending timepoint
    timepoint = Timepoint.create(
        query=request.query,
        status=TimepointStatus.PROCESSING,
    )

    session.add(timepoint)
    await session.commit()
    await session.refresh(timepoint)

    # Start background generation
    background_tasks.add_task(
        run_generation_task,
        timepoint.id,
        request.query,
        None,  # session_factory not needed with get_session()
    )

    return GenerateResponse(
        id=timepoint.id,
        status="processing",
        message=f"Generation started for '{request.query}'",
    )


@router.post("/generate/sync", response_model=TimepointResponse)
async def generate_timepoint_sync(
    request: GenerateRequest,
    session: AsyncSession = Depends(get_db_session),
) -> TimepointResponse:
    """Generate timepoint synchronously.

    Runs the full pipeline and returns completed timepoint.
    Warning: This can take 30-60 seconds.

    Args:
        request: Generation request with query
        session: Database session

    Returns:
        TimepointResponse with full data

    Raises:
        HTTPException: If generation fails
    """
    logger.info(f"Sync generate request: {request.query}")

    try:
        # Run pipeline
        pipeline = GenerationPipeline()
        state = await pipeline.run(request.query)

        # Convert to timepoint
        timepoint = pipeline.state_to_timepoint(state)

        # Save to database
        session.add(timepoint)
        await session.commit()
        await session.refresh(timepoint)

        # Also save generation logs
        logs = pipeline.state_to_generation_logs(state)
        for log in logs:
            session.add(log)
        await session.commit()

        return timepoint_to_response(timepoint, include_full=True)

    except Exception as e:
        logger.error(f"Sync generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{timepoint_id}", response_model=TimepointResponse)
async def get_timepoint(
    timepoint_id: str,
    full: bool = Query(False, description="Include full metadata"),
    session: AsyncSession = Depends(get_db_session),
) -> TimepointResponse:
    """Get timepoint by ID.

    Args:
        timepoint_id: Timepoint UUID
        full: Whether to include full metadata
        session: Database session

    Returns:
        TimepointResponse

    Raises:
        HTTPException: If timepoint not found
    """
    result = await session.execute(
        select(Timepoint).where(Timepoint.id == timepoint_id)
    )
    timepoint = result.scalar_one_or_none()

    if not timepoint:
        raise HTTPException(status_code=404, detail="Timepoint not found")

    return timepoint_to_response(timepoint, include_full=full)


@router.get("/slug/{slug}", response_model=TimepointResponse)
async def get_timepoint_by_slug(
    slug: str,
    full: bool = Query(False, description="Include full metadata"),
    session: AsyncSession = Depends(get_db_session),
) -> TimepointResponse:
    """Get timepoint by slug.

    Args:
        slug: URL-safe slug
        full: Whether to include full metadata
        session: Database session

    Returns:
        TimepointResponse

    Raises:
        HTTPException: If timepoint not found
    """
    result = await session.execute(select(Timepoint).where(Timepoint.slug == slug))
    timepoint = result.scalar_one_or_none()

    if not timepoint:
        raise HTTPException(status_code=404, detail="Timepoint not found")

    return timepoint_to_response(timepoint, include_full=full)


@router.get("", response_model=TimepointListResponse)
async def list_timepoints(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status: str | None = Query(None, description="Filter by status"),
    session: AsyncSession = Depends(get_db_session),
) -> TimepointListResponse:
    """List timepoints with pagination.

    Args:
        page: Page number (1-indexed)
        page_size: Number of items per page
        status: Optional status filter
        session: Database session

    Returns:
        TimepointListResponse with paginated items
    """
    # Build query
    query = select(Timepoint).order_by(Timepoint.created_at.desc())

    if status:
        try:
            status_enum = TimepointStatus(status)
            query = query.where(Timepoint.status == status_enum)
        except ValueError:
            pass  # Invalid status, ignore filter

    # Get total count
    count_result = await session.execute(
        select(Timepoint.id).select_from(query.subquery())
    )
    total = len(count_result.all())

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await session.execute(query)
    timepoints = result.scalars().all()

    return TimepointListResponse(
        items=[timepoint_to_response(tp) for tp in timepoints],
        total=total,
        page=page,
        page_size=page_size,
    )
