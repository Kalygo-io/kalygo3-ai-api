from fastapi import APIRouter

# Import the separate endpoint routers
from .kb_stats import router as kb_stats_router
from .upload import router as upload_router
from .delete_vectors import router as delete_vectors_router
from .search import router as search_router

router = APIRouter()

# Include all the endpoint routers
router.include_router(kb_stats_router)
router.include_router(upload_router)
router.include_router(delete_vectors_router)
# router.include_router(search_router) 