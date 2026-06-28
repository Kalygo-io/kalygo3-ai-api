"""
Credentials router — combines all credential CRUD endpoints (legacy and flexible).
"""
from fastapi import APIRouter

from .create import router as create_router
from .list import router as list_router
from .get import router as get_router
from .update import router as update_router
from .delete import router as delete_router
from .get_by_service import router as get_by_service_router
from .create_flexible import router as create_flexible_router
from .get_full import router as get_full_router
from .update_full import router as update_full_router
from .get_by_service_full import router as get_by_service_full_router

# Sharing (access grants) and per-account default selection
from .share.create_grant import router as share_create_router
from .share.revoke_grant import router as share_revoke_router
from .share.list_grants import router as share_list_router
from .defaults.set_default import router as default_set_router
from .defaults.unset_default import router as default_unset_router

router = APIRouter()

# Legacy CRUD endpoints (order matches original registration)
router.include_router(create_router)
router.include_router(list_router)
router.include_router(get_router)
router.include_router(update_router)
router.include_router(delete_router)
router.include_router(get_by_service_router)

# Flexible credential endpoints
router.include_router(create_flexible_router)
router.include_router(get_full_router)
router.include_router(update_full_router)
router.include_router(get_by_service_full_router)

# Sharing + default-selection endpoints
router.include_router(share_create_router)
router.include_router(share_revoke_router)
router.include_router(share_list_router)
router.include_router(default_set_router)
router.include_router(default_unset_router)
