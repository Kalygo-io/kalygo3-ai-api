"""
Shared test fixtures for the kalygo3-ai-api test suite.

Key design choices:
- POSTGRES_URL is FORCE-SET to the test database URL before any app imports.
  This guarantees tests can never accidentally touch production.
- Each test runs inside a DB transaction that is rolled back, so tests are
  fast and isolated with zero cleanup.
- Auth tokens are minted directly (no login round-trip needed per test).
- External services (Stripe, GCS, PubSub) are not called; dependencies are
  overridden where needed.
"""

import os

# --- FORCE-SET test environment BEFORE any application imports ---
# Uses POSTGRES_TEST_URL if provided, otherwise defaults to local test DB.
# Critically: this OVERWRITES any existing POSTGRES_URL to prevent
# accidental operations against production.
_TEST_DB_URL = os.environ.get(
    "POSTGRES_TEST_URL",
    "postgresql://test:test@localhost:5432/kalygo_test"
)
os.environ["POSTGRES_URL"] = _TEST_DB_URL
os.environ.setdefault("AUTH_SECRET_KEY", "test-secret-key-do-not-use-in-prod")
os.environ.setdefault("AUTH_ALGORITHM", "HS256")
os.environ.setdefault("COOKIE_DOMAIN", "localhost")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_fake")
os.environ.setdefault("PINECONE_API_KEY", "fake-pinecone-key")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")
os.environ.setdefault("SENTRY_DSN", "")
os.environ.setdefault("SENDGRID_API_KEY", "fake")
os.environ.setdefault("EMBEDDINGS_API_URL", "http://localhost:9999")
os.environ.setdefault("KB_INGEST_SA", "{}")
os.environ.setdefault("GCS_BUCKET_NAME", "test-bucket")
os.environ.setdefault("PUBSUB_TOPIC", "test-topic")
os.environ.setdefault("GCP_PROJECT_ID", "test-project")
os.environ.setdefault("CREDENTIAL_ENCRYPTION_KEY", "dGVzdC1lbmNyeXB0aW9uLWtleS0zMi1ieXRlcw==")

from datetime import timedelta, datetime, timezone
from typing import Generator

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from src.db.database import Base
from src.db.models import Account
from src.deps import get_db
from src.main import app


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = os.environ["POSTGRES_URL"]

test_engine = create_engine(
    TEST_DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"connect_timeout": 5},
)

TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def _setup_database():
    """Create all tables (and required PG enum types) once per test session.

    SAFETY: This fixture NEVER drops tables. Schema is additive only.
    Data isolation is handled by per-test transaction rollback.
    """
    # Guard: refuse to run if the URL looks like a production database
    if any(host in TEST_DATABASE_URL for host in ["supabase.co", "neon.tech", "rds.amazonaws.com"]):
        raise RuntimeError(
            f"REFUSING to run tests: POSTGRES_URL points to a production-like host.\n"
            f"  URL: {TEST_DATABASE_URL[:50]}...\n"
            f"  Set POSTGRES_TEST_URL to a local/disposable database."
        )

    with test_engine.connect() as conn:
        conn.execute(text("""
            DO $$ BEGIN
                CREATE TYPE api_key_status_enum AS ENUM ('active', 'revoked');
            EXCEPTION WHEN duplicate_object THEN NULL;
            END $$;
        """))
        conn.execute(text("""
            DO $$ BEGIN
                CREATE TYPE operation_type_enum AS ENUM ('INGEST', 'DELETE', 'UPDATE');
            EXCEPTION WHEN duplicate_object THEN NULL;
            END $$;
        """))
        conn.execute(text("""
            DO $$ BEGIN
                CREATE TYPE operation_status_enum AS ENUM ('SUCCESS', 'FAILED', 'PARTIAL', 'PENDING');
            EXCEPTION WHEN duplicate_object THEN NULL;
            END $$;
        """))
        conn.execute(text("""
            DO $$ BEGIN
                CREATE TYPE emaileventtype AS ENUM (
                    'send', 'send_to_ses', 'delivery', 'open',
                    'bounce', 'complaint', 'click', 'other'
                );
            EXCEPTION WHEN duplicate_object THEN NULL;
            END $$;
        """))
        conn.execute(text("""
            DO $$ BEGIN
                CREATE TYPE credential_type_enum AS ENUM (
                    'OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'GOOGLE_GEMINI_API_KEY',
                    'PINECONE_API_KEY', 'ELEVENLABS_API_KEY', 'SUPABASE',
                    'AWS_SES', 'GOOGLE_OAUTH', 'GOOGLE_GMAIL_SMTP'
                );
            EXCEPTION WHEN duplicate_object THEN NULL;
            END $$;
        """))
        conn.execute(text("""
            DO $$ BEGIN
                CREATE TYPE emailcampaignstatus AS ENUM (
                    'draft', 'active', 'paused', 'completed'
                );
            EXCEPTION WHEN duplicate_object THEN NULL;
            END $$;
        """))
        conn.commit()

    Base.metadata.create_all(bind=test_engine)

    yield
    # No teardown — tables are left in place for inspection and speed.


@pytest.fixture()
def db() -> Generator[Session, None, None]:
    """Provide a transactional DB session that rolls back after each test."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def _override_db(db: Session):
    """Override the app's get_db dependency with the test session."""

    def _get_test_db():
        yield db

    app.dependency_overrides[get_db] = _get_test_db
    yield
    app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# Auth fixtures
# ---------------------------------------------------------------------------

SECRET_KEY = os.environ["AUTH_SECRET_KEY"]
ALGORITHM = os.environ["AUTH_ALGORITHM"]


def make_token(email: str = "test@example.com", user_id: int = 1, hours: int = 12) -> str:
    """Mint a valid JWT for testing."""
    payload = {
        "sub": email,
        "id": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=hours),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


@pytest.fixture()
def test_account(db: Session) -> Account:
    """Insert a test account and return it."""
    account = Account(id=1, email="test@example.com")
    db.add(account)
    db.flush()
    return account


@pytest.fixture()
def auth_token(test_account: Account) -> str:
    """Return a valid JWT for the test account."""
    return make_token(email=test_account.email, user_id=test_account.id)


# ---------------------------------------------------------------------------
# HTTP client fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
async def client(_override_db) -> AsyncClient:
    """Unauthenticated async HTTP client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture()
async def authed_client(_override_db, auth_token: str) -> AsyncClient:
    """Authenticated async HTTP client (JWT in Authorization header)."""
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as ac:
        yield ac
