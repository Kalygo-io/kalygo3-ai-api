"""
Enumeration of supported API service names for credentials storage.
"""
from enum import Enum


class ServiceName(str, Enum):
    """
    Supported API service names for storing credentials.
    
    This enum explicitly defines which third-party API keys are supported
    by the Kalygo platform. New services can be added as needed.
    """
    OPENAI_API_KEY = "OPENAI_API_KEY"
    ANTHROPIC_API_KEY = "ANTHROPIC_API_KEY"
    PINECONE_API_KEY = "PINECONE_API_KEY"

