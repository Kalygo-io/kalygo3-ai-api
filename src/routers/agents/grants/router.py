"""
Agent Access Grants router – aggregates grant sub-routers.
"""
from fastapi import APIRouter
from .create_grant import router as create_grant_router
from .list_grants import router as list_grants_router
from .revoke_grant import router as revoke_grant_router

router = APIRouter()

router.include_router(create_grant_router)
router.include_router(list_grants_router)
router.include_router(revoke_grant_router)
