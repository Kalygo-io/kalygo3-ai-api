from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os

load_dotenv()

SQL_ALCHEMY_DATABASE_URL = os.getenv("POSTGRES_URL")

if not SQL_ALCHEMY_DATABASE_URL:
    raise ValueError("POSTGRES_URL environment variable is required")

# Fix postgres:// -> postgresql:// (SQLAlchemy requirement)
if SQL_ALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQL_ALCHEMY_DATABASE_URL = SQL_ALCHEMY_DATABASE_URL.replace(
        "postgres://", "postgresql://", 1
    )

# Configure connection pool for Supabase Pooler (PgBouncer on port 6543)
# Using pooler allows many more connections than direct (port 5432)
engine = create_engine(
    SQL_ALCHEMY_DATABASE_URL,
    pool_size=5,              # Local pool size (PgBouncer handles actual pooling)
    max_overflow=5,           # Allow up to 5 additional connections
    pool_pre_ping=True,       # Verify connections before using them
    pool_recycle=300,         # Recycle connections every 5 minutes
    pool_timeout=30,          # Wait max 30 seconds for a connection from the pool
    # Required for PgBouncer (Supabase pooler):
    use_native_hstore=False,  # Disable hstore OID lookup (fails with PgBouncer)
    connect_args={
        "sslmode": "require",
        "connect_timeout": 10,
        # TCP keepalives for SSL stability
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 5,
        "application_name": "kalygo3",
    },
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()