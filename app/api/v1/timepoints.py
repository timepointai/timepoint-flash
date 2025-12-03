"""Timepoint API endpoints.

Provides REST API for timepoint generation and retrieval.

Endpoints:
    POST /api/v1/timepoints/generate - Start timepoint generation
    POST /api/v1/timepoints/generate/sync - Synchronous generation
    POST /api/v1/timepoints/generate/stream - SSE streaming generation
    GET /api/v1/timepoints/{id} - Get timepoint by ID
    GET /api/v1/timepoints/slug/{slug} - Get timepoint by slug
    GET /api/v1/timepoints - List timepoints
    DELETE /api/v1/timepoints/{id} - Delete timepoint

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
    - tests/unit/test_api_streaming.py::test_stream_endpoint
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, AsyncGenerator

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import QualityPreset
from app.core.pipeline import GenerationPipeline, PipelineStep
from app.database import get_db_session
from app.models import GenerationLog, Timepoint, TimepointStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/timepoints", tags=["timepoints"])


# Request/Response Models


class GenerateRequest(BaseModel):
    """Request to generate a timepoint.

    Attributes:
        query: The temporal query to generate
        generate_image: Whether to generate the image
        preset: Quality preset (hd, hyper, balanced)
        text_model: Custom text model override (ignores preset)
        image_model: Custom image model override (ignores preset)
    """

    query: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="Temporal query (e.g., 'signing of the declaration')",
        examples=["signing of the declaration", "rome 50 BCE", "battle of thermopylae"],
    )
    generate_image: bool = Field(
        default=False,
        description="Whether to generate an image (adds ~30s)",
    )
    preset: str | None = Field(
        default=None,
        description="Quality preset: 'hd' (best quality), 'hyper' (fastest), 'balanced' (default)",
        examples=["hd", "hyper", "balanced"],
    )
    text_model: str | None = Field(
        default=None,
        description="Custom text model override (e.g., 'google/gemini-2.0-flash-001'). Overrides preset.",
        examples=["google/gemini-2.0-flash-001", "meta-llama/llama-3.1-8b-instruct"],
    )
    image_model: str | None = Field(
        default=None,
        description="Custom image model override (e.g., 'google/imagen-3'). Overrides preset.",
        examples=["google/imagen-3", "black-forest-labs/flux-1.1-pro"],
    )


class StreamEvent(BaseModel):
    """Server-Sent Event for streaming generation.

    Attributes:
        event: Event type (step_start, step_complete, error, done)
        step: Current pipeline step
        data: Event data
        progress: Progress percentage (0-100)
    """

    event: str
    step: str | None = None
    data: dict[str, Any] | None = None
    progress: int = 0
    error: str | None = None


class DeleteResponse(BaseModel):
    """Response after deleting a timepoint."""

    id: str
    deleted: bool
    message: str


class TimepointResponse(BaseModel):
    """Response containing timepoint data.

    Attributes:
        id: Timepoint ID
        query: Original query
        slug: URL-safe slug
        status: Generation status
        year: Temporal year
        location: Geographic location
        has_image: Whether an image was generated
        image_url: Generated image URL (if available)
        image_base64: Base64 image data (only if include_image=true)
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
    has_image: bool = False  # Always included - indicates if image exists
    image_url: str | None = None
    image_base64: str | None = None  # Only included if include_image=true
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


def timepoint_to_response(tp: Timepoint, include_full: bool = False, include_image: bool = False) -> TimepointResponse:
    """Convert Timepoint model to response.

    Args:
        tp: Timepoint model
        include_full: Whether to include full metadata
        include_image: Whether to include base64 image data

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
        has_image=tp.has_image,  # Always include whether image exists
        image_url=tp.image_url,
        image_base64=tp.image_base64 if include_image else None,
        created_at=tp.created_at.isoformat() if tp.created_at else None,
        error=tp.error_message,
    )

    if include_full:
        response.metadata = tp.metadata_json
        response.characters = tp.character_data_json
        response.scene = tp.scene_data_json
        response.dialog = tp.dialog_json

    return response


# SSE Streaming Generator


async def stream_generation(
    query: str,
    generate_image: bool = False,
    preset: QualityPreset | None = None,
    text_model: str | None = None,
    image_model: str | None = None,
) -> AsyncGenerator[str, None]:
    """Generate SSE events for pipeline progress with real-time streaming.

    Yields SSE-formatted events as each pipeline step completes,
    providing real-time progress updates.

    Args:
        query: The query to generate
        generate_image: Whether to generate image
        preset: Quality preset (HD, HYPER, BALANCED)
        text_model: Custom text model override
        image_model: Custom image model override

    Yields:
        SSE-formatted event strings
    """
    # Step mapping with progress percentages
    # Note: Graph is now integrated into Characters step (ID→Graph→Bios)
    # Moment and Camera run in parallel after Characters
    step_progress = {
        PipelineStep.JUDGE: 10,
        PipelineStep.TIMELINE: 20,
        PipelineStep.SCENE: 30,
        PipelineStep.CHARACTERS: 50,  # Includes CharID + Graph + parallel Bios
        PipelineStep.MOMENT: 65,      # Parallel with Camera
        PipelineStep.CAMERA: 65,      # Parallel with Moment
        PipelineStep.GRAPH: 50,       # Legacy (now inside Characters)
        PipelineStep.DIALOG: 80,
        PipelineStep.IMAGE_PROMPT: 90,
        PipelineStep.IMAGE_GENERATION: 100,
    }

    def format_sse(event: StreamEvent) -> str:
        """Format event as SSE."""
        data = event.model_dump_json()
        return f"data: {data}\n\n"

    pipeline = GenerationPipeline(
        preset=preset,
        text_model=text_model,
        image_model=image_model,
    )
    state = None
    start_time = time.perf_counter()

    # Debug log to verify generate_image value
    logger.info(f"Stream generation: query='{query}', generate_image={generate_image}, preset={preset}, text_model={text_model}, image_model={image_model}")

    try:
        # Send start event
        yield format_sse(StreamEvent(
            event="start",
            step="initialization",
            data={"query": query, "generate_image": generate_image},
            progress=0,
        ))

        # Stream pipeline execution - yields after each step completes
        async for step, result, current_state in pipeline.run_streaming(query, generate_image):
            state = current_state  # Keep reference to final state
            progress = step_progress.get(step, 0)

            if result.success:
                yield format_sse(StreamEvent(
                    event="step_complete",
                    step=step.value,
                    data={
                        "latency_ms": result.latency_ms,
                        "model_used": result.model_used,
                    },
                    progress=progress,
                ))
            else:
                yield format_sse(StreamEvent(
                    event="step_error",
                    step=step.value,
                    error=result.error,
                    progress=progress,
                ))

        # Send final result if we have state
        if state is not None:
            total_time = int((time.perf_counter() - start_time) * 1000)
            timepoint = pipeline.state_to_timepoint(state)

            # Save to database
            from app.database import get_session
            saved = False
            try:
                async with get_session() as session:
                    session.add(timepoint)
                    await session.commit()
                    await session.refresh(timepoint)

                    # Also save generation logs
                    logs = pipeline.state_to_generation_logs(state)
                    for log in logs:
                        session.add(log)
                    await session.commit()

                    saved = True
                    logger.info(f"Streaming generation saved: {timepoint.id} ({timepoint.status})")

                    # Send done event ONLY after successful database save
                    yield format_sse(StreamEvent(
                        event="done",
                        step="complete",
                        data={
                            "timepoint_id": timepoint.id,
                            "slug": timepoint.slug,
                            "status": timepoint.status.value,
                            "year": timepoint.year,
                            "location": timepoint.location,
                            "total_latency_ms": total_time,
                            "has_image": state.image_base64 is not None,
                            "saved": True,
                        },
                        progress=100,
                    ))
            except Exception as db_error:
                logger.error(f"Failed to save streaming result: {db_error}")
                # Send error event when database save fails
                yield format_sse(StreamEvent(
                    event="error",
                    step="database_save",
                    error=f"Failed to save timepoint: {db_error}",
                    data={
                        "timepoint_id": timepoint.id,
                        "status": "save_failed",
                        "total_latency_ms": total_time,
                        "saved": False,
                    },
                    progress=100,
                ))

    except Exception as e:
        logger.error(f"Streaming generation failed: {e}")
        yield format_sse(StreamEvent(
            event="error",
            error=str(e),
            progress=0,
        ))


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
        # Parse preset
        preset = None
        if request.preset:
            try:
                preset = QualityPreset(request.preset.lower())
            except ValueError:
                logger.warning(f"Invalid preset '{request.preset}', using default")

        # Run pipeline
        pipeline = GenerationPipeline(
            preset=preset,
            text_model=request.text_model,
            image_model=request.image_model,
        )
        state = await pipeline.run(request.query, request.generate_image)

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
    include_image: bool = Query(False, description="Include base64 image data"),
    session: AsyncSession = Depends(get_db_session),
) -> TimepointResponse:
    """Get timepoint by ID.

    Args:
        timepoint_id: Timepoint UUID
        full: Whether to include full metadata
        include_image: Whether to include base64 image data
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

    return timepoint_to_response(timepoint, include_full=full, include_image=include_image)


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


@router.post("/generate/stream")
async def generate_timepoint_stream(
    request: GenerateRequest,
) -> StreamingResponse:
    """Generate timepoint with SSE streaming progress.

    Returns Server-Sent Events for each pipeline step.
    Use EventSource API or similar to consume the stream.

    Event types:
        - start: Generation started
        - step_complete: A pipeline step completed
        - step_error: A pipeline step failed
        - done: Generation complete with final data
        - error: Fatal error occurred

    Args:
        request: Generation request with query and optional preset

    Returns:
        StreamingResponse with SSE events

    Example:
        ```javascript
        const eventSource = new EventSource('/api/v1/timepoints/generate/stream');
        eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log(data.event, data.progress);
        };
        ```

    Presets:
        - hd: Highest quality (Gemini 3 Pro + Google image gen)
        - hyper: Fastest speed (Llama 8B + fast image gen)
        - balanced: Default balance of quality and speed
    """
    # Parse preset
    preset = None
    if request.preset:
        try:
            preset = QualityPreset(request.preset.lower())
            logger.info(f"Stream generate request: {request.query} (preset: {preset.value})")
        except ValueError:
            logger.warning(f"Invalid preset '{request.preset}', using default")
            logger.info(f"Stream generate request: {request.query}")
    else:
        logger.info(f"Stream generate request: {request.query}")

    return StreamingResponse(
        stream_generation(
            request.query,
            request.generate_image,
            preset,
            text_model=request.text_model,
            image_model=request.image_model,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.delete("/{timepoint_id}", response_model=DeleteResponse)
async def delete_timepoint(
    timepoint_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> DeleteResponse:
    """Delete a timepoint by ID.

    Also deletes associated generation logs.

    Args:
        timepoint_id: Timepoint UUID
        session: Database session

    Returns:
        DeleteResponse confirming deletion

    Raises:
        HTTPException: If timepoint not found
    """
    # Check if exists
    result = await session.execute(
        select(Timepoint).where(Timepoint.id == timepoint_id)
    )
    timepoint = result.scalar_one_or_none()

    if not timepoint:
        raise HTTPException(status_code=404, detail="Timepoint not found")

    # Delete generation logs first
    await session.execute(
        delete(GenerationLog).where(GenerationLog.timepoint_id == timepoint_id)
    )

    # Delete timepoint
    await session.delete(timepoint)
    await session.commit()

    logger.info(f"Deleted timepoint: {timepoint_id}")

    return DeleteResponse(
        id=timepoint_id,
        deleted=True,
        message=f"Timepoint {timepoint_id} deleted successfully",
    )
