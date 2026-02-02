"""
Authentication helpers for agent completion.

Handles extracting authentication tokens from requests for use
with internal APIs (e.g., embedding service).
"""
from typing import Optional
from fastapi import Request


def extract_auth_token(request: Request, auth: dict) -> Optional[str]:
    """
    Extract authentication token from request for passing to internal services.
    
    Handles both JWT and API key authentication methods.
    
    Args:
        request: The FastAPI request object
        auth: The auth dict from the auth dependency
        
    Returns:
        The authentication token (JWT or API key), or None if not found
    """
    if not request:
        return None
    
    auth_type = auth.get('auth_type', 'jwt')
    
    if auth_type == 'jwt':
        return _extract_jwt_token(request)
    elif auth_type == 'api_key':
        return _extract_api_key(request)
    
    return None


def _extract_jwt_token(request: Request) -> Optional[str]:
    """Extract JWT token from cookie or Authorization header."""
    # Try cookie first
    jwt_token = request.cookies.get("jwt")
    
    # If not in cookie, try Authorization header
    if not jwt_token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            jwt_token = auth_header.replace("Bearer ", "").strip()
    
    return jwt_token


def _extract_api_key(request: Request) -> Optional[str]:
    """Extract API key from Authorization header or X-API-Key header."""
    api_key = None
    
    # Check Authorization header: "Bearer kalygo_live_..."
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        api_key = auth_header.replace("Bearer ", "").strip()
    
    # Also check X-API-Key header
    if not api_key:
        api_key = request.headers.get("X-API-Key", "").strip() or None
    
    if api_key:
        print(f"[AUTH] Using API key authentication for internal services")
    
    return api_key
