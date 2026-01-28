"""
Accounts router for managing user accounts.
Provides CRUD operations for the authenticated user's own account only.
"""
from fastapi import APIRouter

# Import endpoint routers
from .get import router as get_router
from .update import router as update_router
from .delete import router as delete_router

router = APIRouter()

# Include endpoint routers
router.include_router(get_router)
router.include_router(update_router)
router.include_router(delete_router)
