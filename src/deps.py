import logging
from typing import Annotated
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException, status, Request
from passlib.context import CryptContext
from jose import jwt, JWTError
import os
from .db.database import SessionLocal
from .db.models import ApiKey, Account, ApiKeyStatus
from .utils.api_key_utils import verify_api_key
from sqlalchemy import func

logger = logging.getLogger(__name__)

SECRET_KEY = os.getenv('AUTH_SECRET_KEY')
ALGORITHM = os.getenv('AUTH_ALGORITHM')

def get_db():
    """
    Database session dependency.
    
    The engine is configured with pool_pre_ping=True and a checkout
    event listener that validates SSL connections, so stale connections
    are automatically replaced before being handed out.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]
bcrypt_context = CryptContext(schemes=["sha256_crypt"])

async def get_current_user(request: Request):
    try:
        token = request.cookies.get("jwt")
        auth_header = request.headers.get("Authorization", "")

        logger.info("[AUTH] %s %s | cookie_jwt: %s | auth_header: %s",
                    request.method, request.url.path,
                    token[:20] + "..." if token else "None",
                    auth_header[:30] + "..." if auth_header else "None")

        if not token:
            if auth_header.startswith("Bearer "):
                token = auth_header.replace("Bearer ", "").strip()

        if not token:
            logger.warning("[AUTH] No token found — rejecting %s %s", request.method, request.url.path)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated - no JWT token found in cookies or Authorization header")

        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        email: str | None = payload.get('sub')
        account_id: str = payload.get('id')
        
        if email is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Could not validate user - email not found in token')
        
        return {'email': email, 'id': account_id}
    except JWTError as e:
        logger.warning("JWT validation failed: %s", e)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f'Could not validate user: {str(e)}')
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error in get_current_user")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f'Could not validate user: {str(e)}')
    
jwt_dependency = Annotated[dict, Depends(get_current_user)]


async def get_current_user_or_api_key(
    request: Request,
    db: Session = Depends(get_db)
) -> dict:
    """
    Unified authentication: tries JWT first, then API key.
    Returns same format: {'email': str, 'id': int, 'auth_type': 'jwt'|'api_key'}
    """
    try:
        token = request.cookies.get("jwt")
        auth_header = request.headers.get("Authorization", "")

        logger.info("[AUTH-UNIFIED] %s %s | cookie_jwt: %s | auth_header: %s",
                    request.method, request.url.path,
                    token[:20] + "..." if token else "None",
                    auth_header[:30] + "..." if auth_header else "None")

        if not token:
            if auth_header.startswith("Bearer "):
                bearer_value = auth_header.replace("Bearer ", "").strip()
                if not bearer_value.startswith("kalygo_"):
                    token = bearer_value

        if token:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            email = payload.get('sub')
            account_id = payload.get('id')
            if email:
                logger.info("[AUTH-UNIFIED] JWT valid for %s", email)
                return {
                    'email': email,
                    'id': int(account_id) if isinstance(account_id, str) else account_id,
                    'auth_type': 'jwt'
                }
    except (JWTError, KeyError, ValueError) as e:
        logger.warning("[AUTH-UNIFIED] JWT decode failed: %s", e)

    api_key = None
    
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        api_key = auth_header.replace("Bearer ", "").strip()
    
    if not api_key:
        api_key = request.headers.get("X-API-Key", "").strip()
    
    if api_key and api_key.startswith("kalygo_"):
        key_prefix = api_key[:20] if len(api_key) >= 20 else api_key
        
        api_key_record = db.query(ApiKey).filter(
            ApiKey.key_prefix == key_prefix,
            ApiKey.status == ApiKeyStatus.ACTIVE
        ).first()
        
        if api_key_record:
            if verify_api_key(api_key, api_key_record.key_hash):
                api_key_record.last_used_at = func.now()
                db.commit()
                
                account = db.query(Account).filter(Account.id == api_key_record.account_id).first()
                if account:
                    return {
                        'email': account.email,
                        'id': api_key_record.account_id,
                        'auth_type': 'api_key',
                        'api_key_id': api_key_record.id,
                    }
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Provide JWT cookie or API key in Authorization/X-API-Key header."
    )


auth_dependency = Annotated[dict, Depends(get_current_user_or_api_key)]


def account_id_from_claims(claims: dict) -> int:
    """Return the integer account id from a JWT / API-key claims dict.

    The ``id`` field may arrive as a string (raw JWT payload) or an int
    (already-coerced unified auth / API-key path); normalize to int.
    """
    account_id = claims['id']
    return int(account_id) if isinstance(account_id, str) else account_id


def ensure_account(db: Session, account_id: int) -> Account:
    """Fetch an account by id, raising 404 if it does not exist."""
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )
    return account