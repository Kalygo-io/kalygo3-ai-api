"""
Agents router for managing AI agents.
Allows creation and management of agents with their configurations.
"""
from fastapi import APIRouter

# Import endpoint routers
from .create import router as create_router
from .list import router as list_router

router = APIRouter()

# Include endpoint routers
router.include_router(create_router)
router.include_router(list_router)
