from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from .routers import (
  healthcheck,
  auth,
  logins,
  waitlist,
  chatAppSessions,
  payments,
  kalygoAgent,
  credentials,
  vectorStores
)

from src.db.database import Base, engine

import debugpy

load_dotenv()

debugpy.listen(("0.0.0.0", 5678))
# debugpy.wait_for_client()

app = FastAPI(docs_url=None, redoc_url=None)

# Let Alembic handle all database schema changes
# Base.metadata.create_all(bind=engine)

origins = [
    "https://kalygo.io",
    "http://127.0.0.1:3000",
    "http://localhost:3000",
    "https://kalygo-nextjs-service-830723611668.us-east1.run.app",
    "https://localhost:3000",
    "http://localhost:5000",  # Second FastAPI
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create a Limiter instance
limiter = Limiter(key_func=get_remote_address)

# Add SlowAPI middleware to FastAPI app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

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

app.include_router(
    kalygoAgent.router,
    prefix="/api/kalygo-agent",
)

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
    chatAppSessions.router,
    prefix="/api/chat-app-sessions",
    tags=['Chat App Sessions'],
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
