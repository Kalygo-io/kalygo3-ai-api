from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os

load_dotenv()

SQL_ALCHEMY_DATABASE_URL = os.getenv("POSTGRES_URL")

# Configure connection pool for Supabase
# Use conservative settings to avoid "Max client connections reached" error
engine = create_engine(
    SQL_ALCHEMY_DATABASE_URL,
    pool_size=3,              # Reduce from default 5 to 3 connections in the pool
    max_overflow=2,           # Allow max 2 additional connections when pool is exhausted
    pool_pre_ping=True,       # Verify connections before using them (handles stale connections)
    pool_recycle=3600,        # Recycle connections after 1 hour
    pool_timeout=30,          # Wait max 30 seconds for a connection from the pool
    echo_pool=False,          # Set to True for debugging connection pool issues
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()