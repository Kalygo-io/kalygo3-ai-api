"""
Contact events router — mounted under /api/contacts/{contact_id}/events
"""
from fastapi import APIRouter

from .create import router as create_router
from .list import router as list_router
from .update import router as update_router
from .delete import router as delete_router

router = APIRouter()

router.include_router(create_router)
router.include_router(list_router)
router.include_router(update_router)
router.include_router(delete_router)
