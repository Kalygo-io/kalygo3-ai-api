from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os
import logging

load_dotenv()

logger = logging.getLogger(__name__)

SQL_ALCHEMY_DATABASE_URL = os.getenv("POSTGRES_URL")

if not SQL_ALCHEMY_DATABASE_URL:
    raise ValueError("POSTGRES_URL environment variable is required")

# Fix postgres:// -> postgresql:// (SQLAlchemy requirement)
if SQL_ALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQL_ALCHEMY_DATABASE_URL = SQL_ALCHEMY_DATABASE_URL.replace(
        "postgres://", "postgresql://", 1
    )

# Connection pool configuration for Supabase Pooler (PgBouncer on port 6543)
#
# Key insight: PgBouncer handles the real connection pooling to Postgres.
# Our local SQLAlchemy pool should be SMALL - it only manages connections
# to PgBouncer, not to Postgres directly. Large local pools create many
# idle connections that Supabase's PgBouncer aggressively kills, causing
# "SSL connection has been closed unexpectedly" errors.
#
# The fix: small pool + short recycle + pre_ping + retry logic in get_db()

DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))
DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "10"))
DB_POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", "30"))
DB_POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "120"))  # 2 min - before PgBouncer kills idle

engine = create_engine(
    SQL_ALCHEMY_DATABASE_URL,
    pool_size=DB_POOL_SIZE,
    max_overflow=DB_MAX_OVERFLOW,
    pool_pre_ping=True,           # Verify connection is alive before checkout
    pool_recycle=DB_POOL_RECYCLE, # Proactively recycle before PgBouncer drops them
    pool_timeout=DB_POOL_TIMEOUT,
    use_native_hstore=False,      # Required for PgBouncer
    connect_args={
        "sslmode": "require",
        "connect_timeout": 10,
        # TCP keepalives - detect dead connections faster
        "keepalives": 1,
        "keepalives_idle": 20,    # Send keepalive after 20s idle
        "keepalives_interval": 5, # Retry every 5s
        "keepalives_count": 3,    # Give up after 3 failures (15s total)
        "application_name": "kalygo3",
    },
)


@event.listens_for(engine, "checkout")
def check_connection(dbapi_connection, connection_record, connection_proxy):
    """
    Verify SSL connection is still alive on checkout.
    If dead, the pool will invalidate it and create a new one.
    """
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
    except Exception:
        # Connection is dead - raise DisconnectionError to force pool to reconnect
        import sqlalchemy.exc
        raise sqlalchemy.exc.DisconnectionError("SSL connection check failed")


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()