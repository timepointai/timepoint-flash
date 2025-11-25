"""
Gallery feed endpoints.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import FeedResponse
from app.models import Timepoint

router = APIRouter()


@router.get("/", response_model=FeedResponse)
async def get_feed(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Get paginated feed of recent timepoints.

    Returns the latest timepoints for the gallery view at /feed.
    ONLY returns completed timepoints with images (filters out in-progress generations).
    """
    from app.schemas import TimepointResponse
    import logging
    logger = logging.getLogger(__name__)

    # Calculate offset
    offset = (page - 1) * per_page

    # Query ONLY completed timepoints with images (filter out in-progress)
    logger.info(f"[FEED_API] Fetching feed - page {page}, per_page {per_page}")

    query = db.query(Timepoint).filter(
        Timepoint.image_url.isnot(None),  # Must have an image
        Timepoint.character_data_json.isnot(None),  # Must have characters
        Timepoint.dialog_json.isnot(None)  # Must have dialog
    )

    timepoints = query.order_by(
        Timepoint.created_at.desc()
    ).offset(offset).limit(per_page).all()

    # Get total count of completed timepoints only
    total = query.count()

    # Check if more pages exist
    has_more = (offset + per_page) < total

    logger.info(f"[FEED_API] Returning {len(timepoints)} completed timepoints (total available: {total})")

    # Convert to schema
    timepoint_responses = []
    for tp in timepoints:
        timepoint_responses.append(TimepointResponse(
            id=tp.id,
            slug=tp.slug,
            year=tp.year,
            season=tp.season,
            input_query=tp.input_query,
            cleaned_query=tp.cleaned_query,
            scene_graph=tp.scene_graph_json,
            characters=tp.character_data_json,
            dialog=tp.dialog_json,
            metadata=tp.metadata_json,
            image_url=tp.image_url,
            segmented_image_url=tp.segmented_image_url,
            processing_time_ms=tp.processing_time_ms,
            created_at=tp.created_at
        ))

    return FeedResponse(
        timepoints=timepoint_responses,
        total=total,
        page=page,
        per_page=per_page,
        has_more=has_more
    )
