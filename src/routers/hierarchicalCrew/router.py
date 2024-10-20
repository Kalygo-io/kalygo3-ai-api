from fastapi import APIRouter
from .healthcheck import router as healthcheck

# Create the main users router
router = APIRouter()

# Include the individual routers from each endpoint file
router.include_router(healthcheck)