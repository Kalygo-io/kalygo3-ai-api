import logging
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from src.middleware.dynamic_cors import DynamicCORSMiddleware
from src.rate_limit import limiter

logger = logging.getLogger(__name__)

from .routers import (
    healthcheck,
    auth,
    logins,
    waitlist,
    chatSessions,
    payments,
    credentials,
    vectorStores,
    agents,
    apiKeys,
    accounts,
    prompts,
    accessGroups,
    similaritySearch,
    contacts,
)
from .routers import contact_lists
from .routers import deals
from .routers import tool_approvals
from .routers import email_events
from .routers import email_templates
from .routers import email_campaigns
from .routers import tracking

app = FastAPI(
    docs_url="/api/docs",
    redoc_url=None,
    redirect_slashes=True,
)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Custom handler for 422 validation errors to provide detailed error messages.
    This helps with debugging API calls from the frontend.
    """
    errors = exc.errors()
    logger.warning("[VALIDATION ERROR] %s %s: %s", request.method, request.url.path, errors)
    
    error_details = []
    for error in errors:
        location = " -> ".join(str(loc) for loc in error["loc"])
        error_details.append({
            "location": location,
            "message": error["msg"],
            "type": error["type"]
        })
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation Error",
            "message": "The request could not be processed due to validation errors.",
            "details": error_details,
            "path": str(request.url.path)
        }
    )


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    """Catch any SQLAlchemy IntegrityError that bubbles past a router."""
    logger.error("[INTEGRITY ERROR] Path: %s | %s: %s", request.url.path, type(exc).__name__, exc)
    orig = getattr(exc, "orig", None)
    msg = str(orig).lower() if orig else str(exc).lower()
    if "unique" in msg or "duplicate" in msg:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": "A record with that value already exists."},
        )
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": "The request conflicts with existing data."},
    )


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError):
    """Catch any other SQLAlchemy error that bubbles past a router."""
    logger.error("[DB ERROR] Path: %s | %s: %s", request.url.path, type(exc).__name__, exc)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "A database error occurred. Please try again."},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Last-resort handler — never let raw exception details reach the client."""
    logger.error("[UNHANDLED] Path: %s | %s: %s", request.url.path, type(exc).__name__, exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected error occurred. Please try again."},
    )


# Allowed origins for JWT/cookie authentication (internal UI)
jwt_allowed_origins = [
    "https://kalygo.io",
    "http://127.0.0.1:3000",
    "http://localhost:3000",
    "https://kalygo-nextjs-service-830723611668.us-east1.run.app",
    "https://localhost:3000",
    "http://localhost:5000",  # Second FastAPI
]

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Dynamic CORS middleware (added last, so runs first to handle OPTIONS preflight)
# - API key requests: Allow all origins (for third-party integrations)
# - JWT/cookie requests: Restrict to jwt_allowed_origins (for internal UI)
app.add_middleware(
    DynamicCORSMiddleware,
    allowed_origins=jwt_allowed_origins,
    allow_credentials=True
)

app.include_router(healthcheck.router, prefix="")

app.include_router(
    auth.router,
    prefix='/api/auth',
    tags=['auth'],
)

app.include_router(
    waitlist.router,
    prefix='/api/waitlist',
    tags=['waitlist'],
)

app.include_router(
    logins.router,
    prefix="/api/logins",
    tags=['logins'],
)

app.include_router(
    similaritySearch.router,  # pyright: ignore[reportUndefinedVariable]
    prefix="/api/similarity-search",
    tags=['Similarity Search'],
)

app.include_router(
    chatSessions.router,
    prefix="/api/chat-sessions",
    tags=['Chat Sessions'],
)

app.include_router(
    payments.router,
    prefix="/api/payments",
    tags=['Payments'],
)

app.include_router(
    credentials.router,
    prefix="/api/credentials",
    tags=['Credentials'],
)

app.include_router(
    vectorStores.router,
    prefix="/api/vector-stores",
    tags=['Vector Stores'],
)

app.include_router(
    agents.router,
    prefix="/api/agents",
    tags=['Agents'],
)

app.include_router(
    apiKeys.router,
    prefix="/api/api-keys",
    tags=['API Keys'],
)

app.include_router(
    accounts.router,
    prefix="/api/accounts",
    tags=['Accounts'],
)

app.include_router(
    prompts.router,
    prefix="/api/prompts",
    tags=['Prompts'],
)

app.include_router(
    accessGroups.router,
    prefix="/api/access-groups",
    tags=['Access Groups'],
)

app.include_router(
    contacts.router,
    prefix="/api/contacts",
    tags=['Contacts'],
)

app.include_router(
    contact_lists.router,
    prefix="/api/contact-lists",
    tags=['Contact Lists'],
)

app.include_router(
    deals.router,
    prefix="/api/deals",
    tags=['Deals'],
)

app.include_router(
    tool_approvals.router,
    prefix="/api/tool-approvals",
    tags=['Tool Approvals'],
)

app.include_router(
    email_events.router,
    prefix="/api/email-events",
    tags=['Email Events'],
)

app.include_router(
    email_templates.router,
    prefix="/api/email-templates",
    tags=['Email Templates'],
)

app.include_router(
    email_campaigns.router,
    prefix="/api/email-campaigns",
    tags=['Email Campaigns'],
)

app.include_router(
    tracking.router,
    prefix="/t",
    tags=['Tracking'],
)
