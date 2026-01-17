"""
API key generation and verification utilities.
"""
import secrets
from passlib.context import CryptContext

# Create bcrypt context for API key hashing
bcrypt_context = CryptContext(schemes=["sha256_crypt"])


def generate_api_key(prefix: str = "kalygo_live") -> tuple[str, str, str]:
    """
    Generate a new API key.
    
    Args:
        prefix: Prefix for the API key (default: "kalygo_live")
    
    Returns:
        (full_key, key_hash, key_prefix)
        - full_key: The complete API key to return to user (only shown once)
        - key_hash: Bcrypt hash to store in database
        - key_prefix: First 20 chars for display/lookup (e.g., "kalygo_live_abc123")
    """
    # Generate random part (32 bytes = ~43 URL-safe chars)
    random_part = secrets.token_urlsafe(32)
    full_key = f"{prefix}_{random_part}"
    
    # Hash the full key
    key_hash = bcrypt_context.hash(full_key)
    
    # Extract prefix for fast lookup (first 20 chars)
    key_prefix = full_key[:20]  # e.g., "kalygo_live_abc123"
    
    return full_key, key_hash, key_prefix


def verify_api_key(plaintext_key: str, key_hash: str) -> bool:
    """
    Verify an API key against its hash.
    
    Args:
        plaintext_key: The plaintext API key to verify
        key_hash: The stored bcrypt hash
    
    Returns:
        True if the key matches, False otherwise
    """
    try:
        return bcrypt_context.verify(plaintext_key, key_hash)
    except Exception:
        return False
