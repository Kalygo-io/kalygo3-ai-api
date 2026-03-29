"""
Contact Lists router — combines all contact list CRUD endpoints and the nested members sub-router.
"""
from fastapi import APIRouter

from .create import router as create_router
from .list import router as list_router
from .get import router as get_router
from .update import router as update_router
from .delete import router as delete_router
from .members.router import router as members_router

router = APIRouter()

router.include_router(create_router)
router.include_router(list_router)
router.include_router(get_router)
router.include_router(update_router)
router.include_router(delete_router)

# Nested members: GET/POST/DELETE /api/contact-lists/{list_id}/members/...
router.include_router(
    members_router,
    prefix="/{list_id}/members",
    tags=["Contact List Members"],
)
