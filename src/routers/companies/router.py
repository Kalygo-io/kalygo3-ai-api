"""
Companies router — combines all company CRUD endpoints and the nested contacts sub-router.
"""
from fastapi import APIRouter

from .create import router as create_router
from .list import router as list_router
from .get import router as get_router
from .update import router as update_router
from .delete import router as delete_router
from .contacts.router import router as contacts_router

router = APIRouter()

router.include_router(create_router)
router.include_router(list_router)
router.include_router(get_router)
router.include_router(update_router)
router.include_router(delete_router)

# Nested contacts: GET/POST/DELETE /api/companies/{company_id}/contacts/...
router.include_router(
    contacts_router,
    prefix="/{company_id}/contacts",
    tags=["Company Contacts"],
)
