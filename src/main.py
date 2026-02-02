from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from src.middleware.dynamic_cors import DynamicCORSMiddleware

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
  prompts
)

from src.db.database import Base, engine

import debugpy

load_dotenv()

debugpy.listen(("0.0.0.0", 5678))
# debugpy.wait_for_client()

# Enable redirect_slashes - we handle HTTPS redirects in CORS middleware
app = FastAPI(
    docs_url="/api/docs", 
    redoc_url=None,
    redirect_slashes=True  # Enable redirects - CORS middleware fixes HTTP->HTTPS redirects
)

# Configure FastAPI to trust proxy headers (for HTTPS detection behind proxies)
# This ensures request.url.scheme is correctly set to 'https' when behind a proxy
app.root_path = ""

# Add custom exception handler for validation errors (422)
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Custom handler for 422 validation errors to provide detailed error messages.
    This helps with debugging API calls from the frontend.
    """
    errors = exc.errors()
    print(f"[VALIDATION ERROR] Path: {request.url.path}")
    print(f"[VALIDATION ERROR] Method: {request.method}")
    print(f"[VALIDATION ERROR] Errors: {errors}")
    
    # Try to log the request body for debugging
    try:
        body = await request.body()
        print(f"[VALIDATION ERROR] Request body: {body.decode('utf-8')[:500]}")
    except:
        pass
    
    # Format error message for frontend
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

# Let Alembic handle all database schema changes
# Base.metadata.create_all(bind=engine)

# Allowed origins for JWT/cookie authentication (internal UI)
jwt_allowed_origins = [
    "https://kalygo.io",
    "http://127.0.0.1:3000",
    "http://localhost:3000",
    "https://kalygo-nextjs-service-830723611668.us-east1.run.app",
    "https://localhost:3000",
    "http://localhost:5000",  # Second FastAPI
]

# Create a Limiter instance
limiter = Limiter(key_func=get_remote_address)

# Add SlowAPI middleware to FastAPI app (runs first)
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

# app.include_router(
#     rawLLM.router,
#     prefix="/api/raw-llm",
# )

# app.include_router(
#     basicMemory.router,
#     prefix="/api/basic-memory",
# )

# app.include_router(
#     persistentMemory.router,
#     prefix="/api/persistent-memory",
# )

# app.include_router(
#     rerankingWithLLM.router,
#     prefix="/api/reranking-with-llm",
# )

# app.include_router(
#     reActAgent.router,
#     prefix="/api/react-agent",
# )

# app.include_router(
#     agenticRagAgent.router,
#     prefix="/api/agentic-rag-agent",
# )

# app.include_router(
#     aiSchoolAgent.router,
#     prefix="/api/ai-school-agent",
# )

# app.include_router(
#     localAgent.router,
#     prefix="/api/local-agent",
# )

# app.include_router(
#     jwtAgent.router,
#     prefix="/api/jwt-agent",
# )

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

# app.include_router(
#     multimodal.router,
#     prefix="/api/multi-modal",
#     tags=['multimodal'],
# )

# app.include_router(
#     similaritySearch.router,
#     prefix="/api/similarity-search",
#     tags=['Similarity Search'],
# )

# app.include_router(
#     reranking.router,
#     prefix="/api/reranking",
#     tags=['Reranking'],
# )

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
