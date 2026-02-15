"""
Access Groups router – aggregates all sub-routers.
"""
from fastapi import APIRouter
from .create import router as create_router
from .list import router as list_router
from .get import router as get_router
from .update import router as update_router
from .delete import router as delete_router
from .add_member import router as add_member_router
from .remove_member import router as remove_member_router
from .list_members import router as list_members_router

router = APIRouter()

router.include_router(create_router)
router.include_router(list_router)
router.include_router(get_router)
router.include_router(update_router)
router.include_router(delete_router)
router.include_router(add_member_router)
router.include_router(remove_member_router)
router.include_router(list_members_router)
