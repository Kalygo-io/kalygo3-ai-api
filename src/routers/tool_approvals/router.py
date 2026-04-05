from fastapi import APIRouter
from .list import router as list_router
from .approve import router as approve_router
from .reject import router as reject_router
from .preview import router as preview_router

router = APIRouter()
router.include_router(list_router)
router.include_router(approve_router)
router.include_router(reject_router)
router.include_router(preview_router)
