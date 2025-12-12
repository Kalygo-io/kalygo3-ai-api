"""
Encryption utility for securely storing and retrieving API keys.
Uses Fernet symmetric encryption from the cryptography library.
Supports key rotation by maintaining multiple encryption keys.
"""
from cryptography.fernet import Fernet, MultiFernet
from dotenv import load_dotenv
import os
import base64
from typing import List, Optional

load_dotenv()

# Get encryption keys from environment variables
# CREDENTIALS_ENCRYPTION_KEY: Current/primary key (required)
# CREDENTIALS_ENCRYPTION_KEY_OLD: Previous key(s) for decryption (optional, comma-separated)
ENCRYPTION_KEY_ENV = os.getenv("CREDENTIALS_ENCRYPTION_KEY")
ENCRYPTION_KEY_OLD_ENV = os.getenv("CREDENTIALS_ENCRYPTION_KEY_OLD", "")

def get_encryption_keys() -> List[bytes]:
    """
    Get encryption keys for Fernet.
    Returns a list of keys: [current_key, old_key1, old_key2, ...]
    The first key is used for encryption, all keys are tried for decryption.
    """
    keys = []
    
    # Get current/primary key
    if ENCRYPTION_KEY_ENV:
        try:
            keys.append(ENCRYPTION_KEY_ENV.encode())
        except Exception:
            key = Fernet.generate_key()
            print(f"WARNING: Invalid encryption key format. Generated new key: {key.decode()}")
            keys.append(key)
    else:
        # Generate a new key (for development only)
        print("WARNING: CREDENTIALS_ENCRYPTION_KEY not set. Generating a new key.")
        print("This key should be saved and set as an environment variable.")
        key = Fernet.generate_key()
        print(f"Generated key (save this): {key.decode()}")
        keys.append(key)
    
    # Get old keys for decryption (for key rotation support)
    if ENCRYPTION_KEY_OLD_ENV:
        old_keys = [k.strip() for k in ENCRYPTION_KEY_OLD_ENV.split(",") if k.strip()]
        for old_key in old_keys:
            try:
                keys.append(old_key.encode())
            except Exception:
                print(f"WARNING: Invalid old encryption key format, skipping: {old_key[:20]}...")
    
    return keys

# Cache for encryption keys (to avoid regenerating on each call)
_cached_keys: Optional[List[bytes]] = None

def _get_cached_keys() -> List[bytes]:
    """Get encryption keys, using cache if available."""
    global _cached_keys
    if _cached_keys is None:
        _cached_keys = get_encryption_keys()
    return _cached_keys

def _get_fernet_cipher() -> Fernet:
    """Get Fernet cipher for encryption (uses current key only)."""
    keys = _get_cached_keys()
    if not keys:
        raise ValueError("No encryption keys available")
    return Fernet(keys[0])

def _get_multi_fernet_cipher() -> MultiFernet:
    """Get MultiFernet cipher for decryption (tries all keys)."""
    keys = _get_cached_keys()
    if not keys:
        raise ValueError("No encryption keys available")
    
    # MultiFernet requires at least one key, and tries them in order
    fernets = [Fernet(key) for key in keys]
    return MultiFernet(fernets)

# Initialize ciphers (lazy initialization)
_fernet: Optional[Fernet] = None
_multi_fernet: Optional[MultiFernet] = None

def _ensure_ciphers_initialized():
    """Ensure ciphers are initialized."""
    global _fernet, _multi_fernet
    if _fernet is None or _multi_fernet is None:
        try:
            _fernet = _get_fernet_cipher()
            _multi_fernet = _get_multi_fernet_cipher()
        except Exception as e:
            # Fallback: generate a new key if initialization fails
            key = Fernet.generate_key()
            _fernet = Fernet(key)
            _multi_fernet = MultiFernet([_fernet])
            print(f"WARNING: Using generated encryption key: {key.decode()}")

def encrypt_api_key(api_key: str) -> str:
    """
    Encrypt an API key using Fernet symmetric encryption.
    
    Args:
        api_key: The plaintext API key to encrypt
        
    Returns:
        The encrypted API key as a base64-encoded string
    """
    if not api_key:
        raise ValueError("API key cannot be empty")
    
    _ensure_ciphers_initialized()
    encrypted_bytes = _fernet.encrypt(api_key.encode())
    return encrypted_bytes.decode()

def decrypt_api_key(encrypted_api_key: str) -> str:
    """
    Decrypt an API key using Fernet symmetric encryption.
    Tries multiple keys to support key rotation.
    
    Args:
        encrypted_api_key: The encrypted API key as a base64-encoded string
        
    Returns:
        The decrypted plaintext API key
    """
    if not encrypted_api_key:
        raise ValueError("Encrypted API key cannot be empty")
    
    _ensure_ciphers_initialized()
    try:
        # MultiFernet tries all keys in order until one succeeds
        decrypted_bytes = _multi_fernet.decrypt(encrypted_api_key.encode())
        return decrypted_bytes.decode()
    except Exception as e:
        raise ValueError(f"Failed to decrypt API key: {str(e)}")

