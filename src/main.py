import logging
import os

# Configure the root logger so application `logger.info(...)` calls actually
# emit. Without this, no root handler exists and Python's last-resort handler
# only shows WARNING+, so all INFO/DEBUG app logs were being silently dropped
# (uvicorn configures only its own loggers, not the root logger).
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

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
from .routers import companies
from .routers import files
from .routers import deals
from .routers import tool_approvals
from .routers import email_events
from .routers import email_templates
from .routers import email_campaigns
from .routers import emails
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
    "https://bolay.kalygo.io",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3002",
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

# Router registration: (router, prefix, tags). Order is preserved from the
# original explicit calls. healthcheck mounts at the root with no tags;
# tracking is mounted under /t. Everything else lives under /api/...
_ROUTERS = [
    (healthcheck.router, "", None),
    (auth.router, "/api/auth", ["auth"]),
    (waitlist.router, "/api/waitlist", ["waitlist"]),
    (logins.router, "/api/logins", ["logins"]),
    (similaritySearch.router, "/api/similarity-search", ["Similarity Search"]),
    (chatSessions.router, "/api/chat-sessions", ["Chat Sessions"]),
    (payments.router, "/api/payments", ["Payments"]),
    (credentials.router, "/api/credentials", ["Credentials"]),
    (vectorStores.router, "/api/vector-stores", ["Vector Stores"]),
    (agents.router, "/api/agents", ["Agents"]),
    (apiKeys.router, "/api/api-keys", ["API Keys"]),
    (accounts.router, "/api/accounts", ["Accounts"]),
    (prompts.router, "/api/prompts", ["Prompts"]),
    (accessGroups.router, "/api/access-groups", ["Access Groups"]),
    (contacts.router, "/api/contacts", ["Contacts"]),
    (contact_lists.router, "/api/contact-lists", ["Contact Lists"]),
    (companies.router, "/api/companies", ["Companies"]),
    (files.router, "/api/files", ["Files"]),
    (deals.router, "/api/deals", ["Deals"]),
    (tool_approvals.router, "/api/tool-approvals", ["Tool Approvals"]),
    (email_events.router, "/api/email-events", ["Email Events"]),
    (email_templates.router, "/api/email-templates", ["Email Templates"]),
    (email_campaigns.router, "/api/email-campaigns", ["Email Campaigns"]),
    (emails.router, "/api/emails", ["Emails"]),
    (tracking.router, "/t", ["Tracking"]),
]

for _router, _prefix, _tags in _ROUTERS:
    app.include_router(_router, prefix=_prefix, tags=_tags)
