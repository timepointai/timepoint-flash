"""API v1 module.

Contains all v1 API routes.

Note: /api/v1/auth/* routes were removed after the Gateway Auth Consolidation
(2026-03-21). Tokens are now issued by the Gateway against the Gateway DB; the
Flash-local routes only 401/500 on real traffic. Clients must call the Gateway
(api.timepointai.com) for all auth operations. See task el-54v9t.
"""

from fastapi import APIRouter

from app.api.v1.content import router as content_router
from app.api.v1.credits import router as credits_router
from app.api.v1.entities import router as entities_router
from app.api.v1.eval import router as eval_router
from app.api.v1.find_money import router as find_money_router
from app.api.v1.interactions import router as interactions_router
from app.api.v1.models import router as models_router
from app.api.v1.openapi_export import router as openapi_export_router
from app.api.v1.reground import router as reground_router
from app.api.v1.tdf import router as tdf_router
from app.api.v1.temporal import router as temporal_router
from app.api.v1.timepoints import router as timepoints_router
from app.api.v1.users import router as users_router

router = APIRouter(prefix="/api/v1")
router.include_router(content_router)
router.include_router(credits_router)
router.include_router(entities_router)
router.include_router(users_router)
router.include_router(timepoints_router)
router.include_router(temporal_router)
router.include_router(models_router)
router.include_router(eval_router)
router.include_router(interactions_router)
router.include_router(openapi_export_router)
router.include_router(tdf_router)
router.include_router(reground_router)
router.include_router(find_money_router)

__all__ = ["router"]
