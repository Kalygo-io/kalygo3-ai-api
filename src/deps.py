from typing import Annotated
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException, status
from passlib.context import CryptContext
from jose import jwt, JWTError
from dotenv import load_dotenv
import os
from .db.database import SessionLocal
from fastapi import Request

load_dotenv()

SECRET_KEY = os.getenv('AUTH_SECRET_KEY')
ALGORITHM = os.getenv('AUTH_ALGORITHM')

def get_db():
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