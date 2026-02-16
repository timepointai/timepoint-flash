"""API v1 module.

Contains all v1 API routes.
"""

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.credits import router as credits_router
from app.api.v1.eval import router as eval_router
from app.api.v1.interactions import router as interactions_router
from app.api.v1.models import router as models_router
from app.api.v1.openapi_export import router as openapi_export_router
from app.api.v1.temporal import router as temporal_router
from app.api.v1.timepoints import router as timepoints_router
from app.api.v1.users import router as users_router

router = APIRouter(prefix="/api/v1")
router.include_router(auth_router)
router.include_router(credits_router)
router.include_router(users_router)
router.include_router(timepoints_router)
router.include_router(temporal_router)
router.include_router(models_router)
router.include_router(eval_router)
router.include_router(interactions_router)
router.include_router(openapi_export_router)

# Optional billing module (only available when timepoint-billing is installed)
try:
    from timepoint_billing import get_billing_router
    router.include_router(get_billing_router())
except ImportError:
    pass

__all__ = ["router"]
