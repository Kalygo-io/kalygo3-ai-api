"""
Dynamic CORS middleware that allows all origins for API key requests
and restricts to specific origins for JWT/cookie requests.
"""
import logging
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from typing import List

logger = logging.getLogger(__name__)


class DynamicCORSMiddleware(BaseHTTPMiddleware):
    """
    CORS middleware that dynamically allows origins based on authentication method:
    - API key requests: Allow all origins
    - JWT/cookie requests: Restrict to specific origins
    """
    
    def __init__(
        self,
        app: ASGIApp,
        allowed_origins: List[str],
        allow_credentials: bool = True
    ):
        super().__init__(app)
        self.allowed_origins = allowed_origins
        self.allow_credentials = allow_credentials
    
    def _has_api_key(self, request: Request) -> bool:
        """Check if request has an API key in headers."""
        # Check Authorization header
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            api_key = auth_header.replace("Bearer ", "").strip()
            if api_key.startswith("kalygo_"):
                return True
        
        # Check X-API-Key header
        api_key = request.headers.get("X-API-Key", "").strip()
        if api_key and api_key.startswith("kalygo_"):
            return True
        
        return False
    
    def _normalize_origin(self, origin: str) -> str:
        """Normalize origin by removing trailing slashes."""
        if origin:
            return origin.rstrip('/')
        return origin
    
    def _is_allowed_origin(self, origin: str) -> bool:
        """Check if origin is in allowed list (with normalization)."""
        if not origin:
            return False
        normalized_origin = self._normalize_origin(origin)
        return normalized_origin in self.allowed_origins or origin in self.allowed_origins
    
    async def dispatch(self, request: Request, call_next):
        """Handle CORS headers based on authentication method."""
        origin = request.headers.get("origin")
        has_api_key = self._has_api_key(request)
        
        # Debug logging - also log the request URL to detect HTTPS->HTTP issues
        request_url = str(request.url) if hasattr(request, 'url') else 'unknown'
        forwarded_proto = request.headers.get("X-Forwarded-Proto", "not-set")
        forwarded_host = request.headers.get("X-Forwarded-Host", "not-set")
        
        if origin:
            is_allowed = self._is_allowed_origin(origin)
            logger.debug("[CORS] %s from origin: %s, has_api_key: %s, is_allowed: %s", request.method, origin, has_api_key, is_allowed)
        
        # Handle preflight OPTIONS requests
        if request.method == "OPTIONS":
            response = Response(status_code=200)
            
            # Strategy:
            # 1. If API key present → allow any origin
            # 2. If origin is in allowed list → allow it (for JWT requests)
            # 3. Otherwise → reject
            
            if has_api_key:
                # API key requests: allow all origins
                if origin:
                    response.headers["Access-Control-Allow-Origin"] = origin
                else:
                    response.headers["Access-Control-Allow-Origin"] = "*"
                response.headers["Access-Control-Allow-Credentials"] = "false"
            elif origin:
                if self._is_allowed_origin(origin):
                    # Allowed origin for JWT requests
                    response.headers["Access-Control-Allow-Origin"] = origin
                    response.headers["Access-Control-Allow-Credentials"] = "true" if self.allow_credentials else "false"
                else:
                    logger.debug("[CORS] Rejecting OPTIONS from origin: %s", origin)
                    response.status_code = 403
                    return response
            else:
                # No origin header (same-origin request) - allow it
                response.headers["Access-Control-Allow-Origin"] = "*"
                response.headers["Access-Control-Allow-Credentials"] = "false"
            
            # Handle Access-Control-Request-Headers if present
            requested_headers = request.headers.get("Access-Control-Request-Headers", "")
            if requested_headers:
                response.headers["Access-Control-Allow-Headers"] = requested_headers
            else:
                response.headers["Access-Control-Allow-Headers"] = "*"
            
            # Handle Access-Control-Request-Method if present
            requested_method = request.headers.get("Access-Control-Request-Method", "")
            if requested_method:
                response.headers["Access-Control-Allow-Methods"] = requested_method
            else:
                response.headers["Access-Control-Allow-Methods"] = "*"
            
            response.headers["Access-Control-Max-Age"] = "3600"
            return response
        
        # Handle actual requests
        response = await call_next(request)
        
        # Fix redirect URLs to use HTTPS if X-Forwarded-Proto indicates HTTPS
        # This prevents mixed content errors when FastAPI redirects
        if response.status_code in (301, 302, 303, 307, 308):
            location = response.headers.get("Location", "")
            if location and forwarded_proto == "https":
                # If we have an HTTP redirect but the request came via HTTPS, fix it
                if location.startswith("http://"):
                    # Replace http:// with https:// in redirect location
                    fixed_location = location.replace("http://", "https://", 1)
                    response.headers["Location"] = fixed_location
                    logger.debug("[CORS] Fixed redirect: %s -> %s", location, fixed_location)
        
        # Add CORS headers to response (including redirect responses)
        if has_api_key:
            # API key requests: allow all origins
            if origin:
                response.headers["Access-Control-Allow-Origin"] = origin
            else:
                response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Credentials"] = "false"
        elif origin:
            if self._is_allowed_origin(origin):
                # Allowed origin for JWT requests
                response.headers["Access-Control-Allow-Origin"] = origin
                response.headers["Access-Control-Allow-Credentials"] = "true" if self.allow_credentials else "false"
            # If origin not in allowed list, don't add CORS headers (browser will block)
        # If no origin header, it's a same-origin request - no CORS headers needed
        
        # Always add these headers if we're adding CORS headers
        if "Access-Control-Allow-Origin" in response.headers:
            response.headers["Access-Control-Allow-Methods"] = "*"
            response.headers["Access-Control-Allow-Headers"] = "*"
        
        return response
