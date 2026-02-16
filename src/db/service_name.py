"""
Enumeration of supported API service names for credentials storage.
"""
from enum import Enum


class ServiceName(str, Enum):
    """
    Supported API service names for storing credentials.
    
    This enum explicitly defines which third-party services are supported
    by the Kalygo platform. New services can be added as needed.
    
    Note: Adding a new value here requires a corresponding Alembic migration
    to add the value to the PostgreSQL enum type.
    """
    # LLM API Keys
    OPENAI_API_KEY = "OPENAI_API_KEY"
    ANTHROPIC_API_KEY = "ANTHROPIC_API_KEY"
    
    # Vector Database
    PINECONE_API_KEY = "PINECONE_API_KEY"
    
    # Voice / Audio
    ELEVENLABS_API_KEY = "ELEVENLABS_API_KEY"
    
    # Database Services
    SUPABASE = "SUPABASE"

