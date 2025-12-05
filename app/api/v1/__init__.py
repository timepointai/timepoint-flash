"""API v1 module.

Contains all v1 API routes.
"""

from fastapi import APIRouter

from app.api.v1.eval import router as eval_router
from app.api.v1.interactions import router as interactions_router
from app.api.v1.models import router as models_router
from app.api.v1.temporal import router as temporal_router
from app.api.v1.timepoints import router as timepoints_router

router = APIRouter(prefix="/api/v1")
router.include_router(timepoints_router)
router.include_router(temporal_router)
router.include_router(models_router)
router.include_router(eval_router)
router.include_router(interactions_router)

__all__ = ["router"]
