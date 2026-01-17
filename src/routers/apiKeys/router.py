"""
API Keys router for managing API keys.
Allows creation and management of API keys for third-party integrations.
"""
from fastapi import APIRouter

# Import endpoint routers
from .create import router as create_router
from .list import router as list_router
from .delete import router as delete_router

router = APIRouter()

# Include endpoint routers
router.include_router(create_router)
router.include_router(list_router)
router.include_router(delete_router)
