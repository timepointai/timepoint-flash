"""API module for TIMEPOINT Flash.

Contains versioned API routers.
"""

from app.api.v1 import router as v1_router

__all__ = ["v1_router"]
