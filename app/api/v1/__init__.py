"""API v1 module.

Contains all v1 API routes.
"""

from fastapi import APIRouter

from app.api.v1.timepoints import router as timepoints_router

router = APIRouter(prefix="/api/v1")
router.include_router(timepoints_router)

__all__ = ["router"]
