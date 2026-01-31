"""Voice Agent API Routes"""

from fastapi import APIRouter

from .webhooks import router as webhooks_router
from .calls import router as calls_router
from .leads import router as leads_router
from .appointments import router as appointments_router
from .tenants import router as tenants_router

# Main router
router = APIRouter(prefix="/voice", tags=["Voice Agent"])

# Include sub-routers
router.include_router(webhooks_router)
router.include_router(calls_router)
router.include_router(leads_router)
router.include_router(appointments_router)
router.include_router(tenants_router)

__all__ = ["router"]
