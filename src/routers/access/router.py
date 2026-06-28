"""Access audit router."""
from fastapi import APIRouter

from .audit import router as audit_router

router = APIRouter()
router.include_router(audit_router)
