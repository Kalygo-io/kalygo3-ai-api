"""
Prompts router - combines all prompt CRUD endpoints.
"""
from fastapi import APIRouter

from .create import router as create_router
from .list import router as list_router
from .get import router as get_router
from .update import router as update_router
from .delete import router as delete_router

router = APIRouter()

# Include all sub-routers
router.include_router(create_router)
router.include_router(list_router)
router.include_router(get_router)
router.include_router(update_router)
router.include_router(delete_router)
