"""
Timepoint creation and status endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Form, Request, Body
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse
import asyncio
import json
from datetime import datetime, timedelta
import uuid
import logging

from app.database import get_db
from app.schemas import (
    ProcessingStatus
)
from app.models import ProcessingSession, Email, RateLimit, Timepoint
from app.utils.rate_limiter import check_rate_limit, check_ip_rate_limit, update_ip_rate_limit
from app.agents.graph_orchestrator import run_timepoint_workflow

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/create")
async def create_timepoint(
    request: Request,
    input_query: str = Body(..., min_length=5, max_length=500, embed=True, alias="input_query"),
    requester_email: str | None = Body(None, embed=True, alias="requester_email"),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """
    Create a new timepoint from user input.

    Public API - No authentication required!

    Rate limiting:
    - With email: 1 timepoint/hour per email
    - Anonymous (no email): 10 timepoints/hour per IP
    - Trusted hosts (*.replit.dev, timepointai.com): Unlimited

    Args:
        input_query: Historical scene description (required)
        requester_email: Email address for rate limiting (optional)

    Returns:
        session_id and initial status
    """
    # Get client IP and host
    client_ip = request.client.host if request.client else "unknown"
    host = request.headers.get("host", "")

    # Check IP-based rate limit (always check for spam protection)
    ip_allowed, ip_error_msg = check_ip_rate_limit(db, client_ip, host)
    if not ip_allowed:
        raise HTTPException(status_code=429, detail=ip_error_msg)

    # If email provided, also check email-based rate limit
    if requester_email:
        email_allowed, email_error_msg = check_rate_limit(db, requester_email, host)
        if not email_allowed:
            raise HTTPException(status_code=429, detail=email_error_msg)
        email_for_db = requester_email
    else:
        # Use anonymous email tied to IP
        email_for_db = f"anonymous-{client_ip}@timepoint.local"

    # Get or create email record
    email_obj = db.query(Email).filter(Email.email == email_for_db).first()
    if not email_obj:
        email_obj = Email(email=email_for_db)
        db.add(email_obj)
        db.commit()
        db.refresh(email_obj)

    # Create processing session
    session_id = str(uuid.uuid4())
    session = ProcessingSession(
        session_id=session_id,
        email=email_for_db,
        status=ProcessingStatus.PENDING,
        progress_data_json={"stage": "initializing", "message": "Starting timepoint generation..."},
        expires_at=datetime.utcnow() + timedelta(hours=1)
    )
    db.add(session)
    db.commit()

    # Update rate limits (both IP and email if provided)
    update_ip_rate_limit(db, client_ip)
    if requester_email:
        from app.utils.rate_limiter import update_rate_limit
        update_rate_limit(db, requester_email)

    # Launch workflow in background
    logger.info(f"Launching workflow for session {session_id}, email: {email_for_db}, IP: {client_ip}")

    async def wrapper():
        """Wrapper to catch any exceptions in background task."""
        try:
            await run_timepoint_workflow(session_id, email_for_db, input_query)
        except Exception as e:
            logger.error(f"Background task FAILED: {e}", exc_info=True)

    background_tasks.add_task(wrapper)

    # Generate slug for response (will be finalized by workflow)
    temp_slug = f"generating-{session_id[:8]}"

    return {
        "session_id": session_id,
        "slug": temp_slug,
        "status": ProcessingStatus.PENDING.value,
        "message": "Timepoint generation started"
    }


@router.get("/status/{session_id}")
async def timepoint_status_stream(session_id: str, db: Session = Depends(get_db)):
    """
    Server-Sent Events stream for timepoint generation progress.
    """
    async def event_generator():
        last_status = None
        last_progress_json = None

        while True:
            # Fetch session from database with aggressive refresh
            db.expire_all()  # Ensure we see latest changes
            db.commit()  # Close any pending transaction to see latest committed data
            session = db.query(ProcessingSession).filter(
                ProcessingSession.session_id == session_id
            ).first()

            if not session:
                yield {
                    "event": "error",
                    "data": json.dumps({"error": "Session not found"})
                }
                yield {
                    "event": "close",
                    "data": ""
                }
                break

            # Convert progress to JSON string for reliable comparison
            current_progress_json = json.dumps(session.progress_data_json, sort_keys=True) if session.progress_data_json else None

            # Send update if status OR progress data changed
            if session.status != last_status or current_progress_json != last_progress_json:
                yield {
                    "event": "status",
                    "data": json.dumps({
                        "session_id": session_id,
                        "status": session.status.value,
                        "progress": session.progress_data_json,
                        "error": session.error_message,
                        "timepoint_id": str(session.timepoint_id) if session.timepoint_id else None
                    })
                }
                last_status = session.status
                last_progress_json = current_progress_json

            # Send gallery preview during processing
            if session.status in [ProcessingStatus.VALIDATING, ProcessingStatus.GENERATING_SCENE]:
                # TODO: Fetch recent timepoints for gallery
                yield {
                    "event": "gallery",
                    "data": json.dumps({"timepoints": []})
                }

            # Break if completed or failed - send close event to stop HTMX from reconnecting
            if session.status in [ProcessingStatus.COMPLETED, ProcessingStatus.FAILED]:
                yield {
                    "event": "close",
                    "data": ""
                }
                break

            await asyncio.sleep(0.3)  # Poll every 300ms for faster detection

    return EventSourceResponse(event_generator())


@router.get("/rate-limit/{email}")
async def get_rate_limit_status(email: str, request: Request, db: Session = Depends(get_db)):
    """
    Get rate limit status for an email address.
    """
    host = request.headers.get("host", "")
    is_allowed, error_msg = check_rate_limit(db, email, host)

    # Get rate limit record
    email_obj = db.query(Email).filter(Email.email == email).first()

    if not email_obj:
        return {
            "available": True,
            "seconds_remaining": 0,
            "next_available_at": None,
            "message": "Ready to create your first timepoint!"
        }

    rate_limit = db.query(RateLimit).filter(RateLimit.email_id == email_obj.id).first()

    if not rate_limit or not rate_limit.last_created_at:
        return {
            "available": True,
            "seconds_remaining": 0,
            "next_available_at": None,
            "message": "Ready to create a timepoint!"
        }

    # Calculate time remaining
    time_since_last = datetime.utcnow() - rate_limit.last_created_at
    seconds_since_last = int(time_since_last.total_seconds())
    seconds_remaining = max(0, 3600 - seconds_since_last)  # 1 hour = 3600 seconds
    next_available_at = rate_limit.last_created_at + timedelta(hours=1)

    return {
        "available": is_allowed,
        "seconds_remaining": seconds_remaining,
        "next_available_at": next_available_at.isoformat() if seconds_remaining > 0 else None,
        "message": error_msg if not is_allowed else "Ready to create a timepoint!"
    }


@router.post("/retry/{slug}")
async def retry_failed_timepoint(
    slug: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Self-healing endpoint: Retry a failed or stalled timepoint generation.
    """
    logger.info(f"[RETRY] Attempting to retry timepoint: {slug}")

    # Find the timepoint
    timepoint = db.query(Timepoint).filter(Timepoint.slug == slug).first()

    if not timepoint:
        logger.warning(f"[RETRY] Timepoint not found: {slug}")
        raise HTTPException(status_code=404, detail="Timepoint not found")

    # Find any existing processing sessions
    sessions = db.query(ProcessingSession).filter(
        ProcessingSession.timepoint_id == timepoint.id
    ).order_by(ProcessingSession.created_at.desc()).all()

    # Mark all old sessions as failed
    for old_session in sessions:
        if old_session.status not in [ProcessingStatus.COMPLETED, ProcessingStatus.FAILED]:
            logger.info(f"[RETRY] Marking stalled session {old_session.session_id} as failed")
            old_session.status = ProcessingStatus.FAILED
            old_session.error_message = "Workflow stalled - automatically restarted"
            old_session.completed_at = datetime.utcnow()

    db.commit()

    # Get original email (use email from most recent session, or default)
    original_email = sessions[0].email if sessions else "retry@timepointai.com"

    # Create a new processing session
    new_session_id = str(uuid.uuid4())
    new_session = ProcessingSession(
        session_id=new_session_id,
        email=original_email,
        timepoint_id=timepoint.id,  # Link to existing timepoint
        status=ProcessingStatus.PENDING,
        progress_data_json={"stage": "retry", "message": "Restarting timepoint generation..."},
        expires_at=datetime.utcnow() + timedelta(hours=1)
    )
    db.add(new_session)
    db.commit()

    logger.info(f"[RETRY] Created new session {new_session_id} for timepoint {slug}")

    # Restart workflow in background with original query
    original_query = timepoint.cleaned_query  # Use the cleaned query from judge

    async def retry_wrapper():
        """Wrapper to catch exceptions in retry workflow."""
        try:
            logger.info(f"[RETRY] Launching retry workflow for {slug}")
            await run_timepoint_workflow(new_session_id, original_email, original_query)
        except Exception as e:
            logger.error(f"[RETRY] Retry workflow FAILED for {slug}: {e}", exc_info=True)
            # Mark session as failed
            retry_session = db.query(ProcessingSession).filter(
                ProcessingSession.session_id == new_session_id
            ).first()
            if retry_session:
                retry_session.status = ProcessingStatus.FAILED
                retry_session.error_message = f"Retry failed: {str(e)}"
                retry_session.completed_at = datetime.utcnow()
                db.commit()

    background_tasks.add_task(retry_wrapper)

    return {
        "success": True,
        "message": "Timepoint generation restarted",
        "slug": slug,
        "new_session_id": new_session_id,
        "timepoint_url": f"/{timepoint.year}/{timepoint.season}/{slug.replace(f'{timepoint.year}-{timepoint.season}-', '')}"
    }


@router.get("/details/{year}/{season}/{slug}")
async def get_timepoint_details(year: int, season: str, slug: str, db: Session = Depends(get_db)):
    """
    Get complete details for a timepoint.
    """
    full_slug = f"{year}-{season}-{slug}"
    
    db.expire_all()
    timepoint = db.query(Timepoint).filter(Timepoint.slug == full_slug).first()
    
    if not timepoint:
        raise HTTPException(status_code=404, detail="Timepoint not found")
        
    db.refresh(timepoint)
    
    return timepoint


@router.get("/check/{slug}")
async def check_timepoint_status(slug: str, db: Session = Depends(get_db)):
    """
    Lightweight JSON endpoint for polling timepoint completion status.
    """
    # CRITICAL: Expire all cached objects to force fresh database read
    db.expire_all()

    # Query timepoint by slug
    timepoint = db.query(Timepoint).filter(Timepoint.slug == slug).first()

    if not timepoint:
        raise HTTPException(status_code=404, detail="Timepoint not found")

    # Force refresh from database
    db.refresh(timepoint)

    # Check individual field completeness
    has_image = bool(
        timepoint.image_url and
        isinstance(timepoint.image_url, str) and
        len(timepoint.image_url) > 0
    )

    has_characters = bool(
        timepoint.character_data_json and
        isinstance(timepoint.character_data_json, list) and
        len(timepoint.character_data_json) > 0
    )

    has_dialog = bool(
        timepoint.dialog_json and
        isinstance(timepoint.dialog_json, list) and
        len(timepoint.dialog_json) > 0
    )

    has_segmented_image = bool(
        timepoint.segmented_image_url and
        isinstance(timepoint.segmented_image_url, str) and
        len(timepoint.segmented_image_url) > 0
    )

    has_metadata = bool(
        timepoint.metadata_json and
        isinstance(timepoint.metadata_json, dict)
    )

    # Consider complete if has all core data (image + characters + dialog)
    is_complete = has_image and has_characters and has_dialog

    # Backup check: Also check ProcessingSession status
    try:
        session = db.query(ProcessingSession).filter(
            ProcessingSession.timepoint_id == timepoint.id
        ).order_by(ProcessingSession.created_at.desc()).first()

        if session and session.status == ProcessingStatus.COMPLETED:
            is_complete = True
    except Exception as e:
        logger.warning(f"[STATUS_CHECK] Failed to check session status: {e}")

    # Calculate permalink URL
    url_slug = slug.replace(f"{timepoint.year}-{timepoint.season}-", "", 1)
    timepoint_url = f"/{timepoint.year}/{timepoint.season}/{url_slug}"

    # Return actual data for progressive display
    response_data = {
        "is_complete": is_complete,
        "has_image": has_image,
        "has_characters": has_characters,
        "has_dialog": has_dialog,
        "has_segmented_image": has_segmented_image,
        "has_metadata": has_metadata,
        "timepoint_url": timepoint_url,
        "slug": slug,
        "image_url": timepoint.image_url if has_image else None,
        "character_data": timepoint.character_data_json if has_characters else None,
        "dialog_data": timepoint.dialog_json if has_dialog else None,
        "segmented_image_url": timepoint.segmented_image_url if has_segmented_image else None,
        "metadata": timepoint.metadata_json if has_metadata else None,
        "year": timepoint.year,
        "season": timepoint.season,
        "cleaned_query": timepoint.cleaned_query
    }

    return response_data
