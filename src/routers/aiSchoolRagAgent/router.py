from fastapi import APIRouter

# Import the separate endpoint routers
from .kb_stats import router as kb_stats_router
from .completion import router as completion_router

router = APIRouter()

# Include all the endpoint routers
router.include_router(kb_stats_router)
router.include_router(completion_router)