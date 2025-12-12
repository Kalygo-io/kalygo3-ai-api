from fastapi import APIRouter

# Import the separate endpoint routers
from .kb_stats import router as kb_stats_router
from .completion import router as completion_router

from .upload_csv import router as upload_csv_router
from .upload_text import router as upload_text_router
from .delete_vectors import router as delete_vectors_router
from .search import router as search_router
from .delete_messages import router as delete_messages_router

router = APIRouter()

# Include all the endpoint routers
router.include_router(kb_stats_router)
router.include_router(completion_router)

router.include_router(upload_csv_router)
router.include_router(upload_text_router)
router.include_router(delete_vectors_router)
router.include_router(search_router)
router.include_router(delete_messages_router) 