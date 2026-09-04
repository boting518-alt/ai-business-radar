"""Version 1 route composition."""

from fastapi import APIRouter

from .admin import router as admin_router
from .auth import router as auth_router
from .health import router as health_router

router = APIRouter(prefix="/api/v1")
router.include_router(health_router)
router.include_router(auth_router)
router.include_router(admin_router)
