from typing import Annotated
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException, status
from passlib.context import CryptContext
from jose import jwt, JWTError
from dotenv import load_dotenv
import os
from .db.database import SessionLocal
from fastapi import Request
from .db.models import ApiKey, Account, ApiKeyStatus
from sqlalchemy import func

load_dotenv()

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
        
        if not token:
            print('--- No JWT token found in cookies ---')
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated - no JWT token found in cookies")

        
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        email: str | None = payload.get('sub')
        account_id: str = payload.get('id')
        
        print(f'--- email (sub): {email} ---')
        print(f'--- account_id: {account_id} ---')
        
        if email is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Could not validate user - email not found in token')
        
        return {'email': email, 'id': account_id}
    except JWTError as e:
        print(f'--- JWT Error: {str(e)} ---')
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f'Could not validate user: {str(e)}')
    except HTTPException:
        raise
    except Exception as e:
        print(f'--- Unexpected error in get_current_user: {str(e)} ---')
        import traceback
        print(f'--- Traceback: {traceback.format_exc()} ---')
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
    # Try JWT first (existing flow)
    try:
        token = request.cookies.get("jwt")
        if token:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            email = payload.get('sub')
            account_id = payload.get('id')
            if email:
                return {
                    'email': email,
                    'id': int(account_id) if isinstance(account_id, str) else account_id,
                    'auth_type': 'jwt'
                }
    except (JWTError, KeyError, ValueError):
        pass
    
    # Try API key from headers
    api_key = None
    
    # Check Authorization header: "Bearer kalygo_live_..."
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        api_key = auth_header.replace("Bearer ", "").strip()
    
    # Also check X-API-Key header
    if not api_key:
        api_key = request.headers.get("X-API-Key", "").strip()
    
    if api_key and api_key.startswith("kalygo_"):
        # Extract prefix for fast lookup
        key_prefix = api_key[:20] if len(api_key) >= 20 else api_key
        
        # Query by prefix first (fast), then verify hash
        api_key_record = db.query(ApiKey).filter(
            ApiKey.key_prefix == key_prefix,
            ApiKey.status == ApiKeyStatus.ACTIVE
        ).first()
        
        if api_key_record:
            # Verify the full key against hash
            from .utils.api_key_utils import verify_api_key
            if verify_api_key(api_key, api_key_record.key_hash):
                # Update last_used_at
                api_key_record.last_used_at = func.now()
                db.commit()
                
                # Get account email
                account = db.query(Account).filter(Account.id == api_key_record.account_id).first()
                if account:
                    return {
                        'email': account.email,
                        'id': api_key_record.account_id,
                        'auth_type': 'api_key',
                        'api_key_id': api_key_record.id  # Useful for logging
                    }
    
    # No valid auth found
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Provide JWT cookie or API key in Authorization/X-API-Key header."
    )


# New unified dependency
auth_dependency = Annotated[dict, Depends(get_current_user_or_api_key)]