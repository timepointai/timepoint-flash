"""
Gallery web UI routes.

Provides HTMX-powered web interface for viewing and generating timepoints.
"""
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path

from app.database import get_db
from app.models import Timepoint
from app.schemas import TimepointResponse

router = APIRouter()

# Setup templates
templates_dir = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("/", response_class=HTMLResponse)
async def gallery_home(
    request: Request,
    page: int = 1,
    db: Session = Depends(get_db)
):
    """
    Gallery home page - displays all timepoints in a grid.
    """
    per_page = 20
    offset = (page - 1) * per_page

    # Query completed timepoints
    query = db.query(Timepoint).filter(
        Timepoint.image_url.isnot(None),
        Timepoint.character_data_json.isnot(None),
        Timepoint.dialog_json.isnot(None)
    )

    timepoints = query.order_by(
        Timepoint.created_at.desc()
    ).offset(offset).limit(per_page).all()

    total = query.count()
    has_more = (offset + per_page) < total

    return templates.TemplateResponse(
        "gallery.html",
        {
            "request": request,
            "timepoints": timepoints,
            "page": page,
            "has_more": has_more,
            "total": total
        }
    )


@router.get("/view/{slug}", response_class=HTMLResponse)
async def view_timepoint(
    request: Request,
    slug: str,
    db: Session = Depends(get_db)
):
    """
    Single timepoint viewer - detailed view with all data.
    """
    timepoint = db.query(Timepoint).filter(Timepoint.slug == slug).first()

    if not timepoint:
        raise HTTPException(status_code=404, detail="Timepoint not found")

    return templates.TemplateResponse(
        "viewer.html",
        {
            "request": request,
            "timepoint": timepoint
        }
    )


@router.get("/generate", response_class=HTMLResponse)
async def generate_form(request: Request):
    """
    Interactive generation form with live SSE updates.
    """
    return templates.TemplateResponse(
        "generate.html",
        {
            "request": request
        }
    )


@router.get("/demo", response_class=HTMLResponse)
async def demo_page(request: Request):
    """
    Demo landing page - explains Timepoint Flash.
    """
    demo_queries = [
        "Medieval marketplace in London, winter 1250",
        "Ancient Rome forum, summer 50 BCE",
        "American Revolutionary War, Valley Forge 1777",
    ]

    return templates.TemplateResponse(
        "demo.html",
        {
            "request": request,
            "demo_queries": demo_queries
        }
    )


# HTMX partial endpoints for dynamic loading
@router.get("/partials/timepoint-card/{slug}", response_class=HTMLResponse)
async def timepoint_card_partial(
    request: Request,
    slug: str,
    db: Session = Depends(get_db)
):
    """
    HTMX partial - single timepoint card for grid.
    """
    timepoint = db.query(Timepoint).filter(Timepoint.slug == slug).first()

    if not timepoint:
        return HTMLResponse(content="", status_code=404)

    return templates.TemplateResponse(
        "partials/timepoint_card.html",
        {
            "request": request,
            "timepoint": timepoint
        }
    )


@router.get("/partials/feed-page", response_class=HTMLResponse)
async def feed_page_partial(
    request: Request,
    page: int = 1,
    db: Session = Depends(get_db)
):
    """
    HTMX partial - next page of timepoints for infinite scroll.
    """
    per_page = 20
    offset = (page - 1) * per_page

    query = db.query(Timepoint).filter(
        Timepoint.image_url.isnot(None),
        Timepoint.character_data_json.isnot(None),
        Timepoint.dialog_json.isnot(None)
    )

    timepoints = query.order_by(
        Timepoint.created_at.desc()
    ).offset(offset).limit(per_page).all()

    total = query.count()
    has_more = (offset + per_page) < total

    return templates.TemplateResponse(
        "partials/feed_page.html",
        {
            "request": request,
            "timepoints": timepoints,
            "page": page + 1,
            "has_more": has_more
        }
    )
