"""
Files router — per-account file storage on Google Cloud Storage.
"""
from fastapi import APIRouter

from .upload import router as upload_router
from .signed_url import router as signed_url_router
from .source_url import router as source_url_router

router = APIRouter()

router.include_router(upload_router)
router.include_router(signed_url_router)
router.include_router(source_url_router)
