from fastapi import APIRouter

router = APIRouter(prefix="/content", tags=["Content"])


@router.get("/today")
async def content_today():
    """Daily curated content. Returns empty when no content is available."""
    return {"items": []}


@router.get("/weekly-prompt")
async def content_weekly_prompt():
    """Weekly creative prompt. Returns null when no prompt is active."""
    return {"prompt": None}


@router.get("/featured")
async def content_featured():
    """Featured timepoints collection. Returns empty when none are featured."""
    return {"items": []}
