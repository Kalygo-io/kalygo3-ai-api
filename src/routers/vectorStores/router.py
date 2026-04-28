"""
Vector Stores router — combines all vector store endpoints and nested sub-routers.
"""
from fastapi import APIRouter

from .list_indexes import router as list_indexes_router
from .create_index import router as create_index_router
from .list_namespaces import router as list_namespaces_router
from .create_namespace import router as create_namespace_router
from .delete_vectors import router as delete_vectors_router
from .list_index_ingestion_logs import router as list_index_ingestion_logs_router
from .ingestion_logs import router as ingestion_logs_router
from .upload import router as upload_router

router = APIRouter()

router.include_router(list_indexes_router)
router.include_router(create_index_router)
router.include_router(list_namespaces_router)
router.include_router(create_namespace_router)
router.include_router(delete_vectors_router)
router.include_router(list_index_ingestion_logs_router)
router.include_router(ingestion_logs_router)
router.include_router(upload_router)
