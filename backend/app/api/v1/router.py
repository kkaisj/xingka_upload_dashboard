from fastapi import APIRouter

from .config import router as config_router
from .health import router as health_router
from .monitor import router as monitor_router
from .scheduler import router as scheduler_router

router = APIRouter(prefix="/api/v1")
router.include_router(config_router)
router.include_router(health_router)
router.include_router(monitor_router)
router.include_router(scheduler_router)
