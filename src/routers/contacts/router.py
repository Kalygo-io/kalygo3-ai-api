"""
Contacts router — combines all contact CRUD endpoints and the nested events sub-router.
"""
from fastapi import APIRouter

from .create import router as create_router
from .list import router as list_router
from .get import router as get_router
from .update import router as update_router
from .delete import router as delete_router
from .events.router import router as events_router
from .career_timeline.router import router as career_timeline_router

router = APIRouter()

router.include_router(create_router)
router.include_router(list_router)
router.include_router(get_router)
router.include_router(update_router)
router.include_router(delete_router)

# Nested events: GET/POST/PUT/DELETE /api/contacts/{contact_id}/events/...
router.include_router(
    events_router,
    prefix="/{contact_id}/events",
    tags=["Contact Events"],
)

# Nested career timeline: GET/POST/PUT/DELETE /api/contacts/{contact_id}/career-timeline/...
router.include_router(
    career_timeline_router,
    prefix="/{contact_id}/career-timeline",
    tags=["Career Timeline"],
)
