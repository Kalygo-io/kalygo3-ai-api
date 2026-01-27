from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os

load_dotenv()

SQL_ALCHEMY_DATABASE_URL = os.getenv("POSTGRES_URL")

# Configure connection pool for Supabase
# Increased pool size to handle concurrent streaming requests
# Each streaming request may hold a connection for the duration of the response
engine = create_engine(
    SQL_ALCHEMY_DATABASE_URL,
    pool_size=10,             # Increased from 3 to handle concurrent requests
    max_overflow=10,          # Allow up to 10 additional connections when pool is exhausted
    pool_pre_ping=True,       # Verify connections before using them (handles stale connections)
    pool_recycle=1800,        # Recycle connections after 30 minutes (reduced from 1 hour)
    pool_timeout=30,          # Wait max 30 seconds for a connection from the pool
    echo_pool=False,          # Set to True for debugging connection pool issues
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()