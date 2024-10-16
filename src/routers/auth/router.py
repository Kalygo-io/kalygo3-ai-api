from datetime import timedelta, datetime, timezone
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Header, Response, BackgroundTasks, Request
from pydantic import BaseModel
from jose import jwt
from dotenv import load_dotenv
import os
from src.db.models import Account
from src.routers.auth.background_tasks import record_login
from src.routers.auth.background_tasks.send_reset_password_link_email_ses import send_reset_password_link_email_ses
from src.routers.auth.background_tasks.send_password_has_been_reset_email_ses import send_password_has_been_reset_email_ses
from src.deps import db_dependency, bcrypt_context

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

load_dotenv()

router = APIRouter()

SECRET_KEY = os.getenv("AUTH_SECRET_KEY")
ALGORITHM = os.getenv("AUTH_ALGORITHM")

class AccountCreateRequestBody(BaseModel):
    email: str
    password: str

class LoginRequestBody(BaseModel):
    email: str
    password: str

class RequestPasswordResetBody(BaseModel):
    email: str

class PasswordResetBody(BaseModel):
    accountId: int
    resetToken: str
    newPassword: str

class Token(BaseModel):
    access_token: str
    token_type: str

def authenticate(email: str, password: str, db):
    print("authenticate...")

    account = db.query(Account).filter(Account.email == email).first()
    if not account:
        return False
    
    if not bcrypt_context.verify(password, account.hashed_password):
        return False
    return account

def create_access_token(username: str, user_id: int, expires_delta: timedelta):
    encode = {'sub': username, 'id': user_id}
    expires = datetime.now(timezone.utc) + expires_delta
    encode.update({'exp': expires})
    return jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)

@router.post("/create-account", status_code=status.HTTP_201_CREATED)
async def create_account(db: db_dependency, create_account_request: AccountCreateRequestBody, request: Request):
    try:
        hashed_password = bcrypt_context.hash(create_account_request.password)
        create_account_model = Account(
            email=create_account_request.email,
            hashed_password=hashed_password
        )
        db.add(create_account_model)
        db.commit()
        db.refresh(create_account_model)
    except Exception as e:
        print('create_user error', e)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    

@router.post('/log-in')
@limiter.limit("5/minute")
async def login_for_access_token(body: LoginRequestBody, db: db_dependency, request: Request, background_tasks: BackgroundTasks):
    print('calling authenticate()...')

    account = authenticate(body.email, body.password, db)
    if not account:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate user")
    
    print("1")

    print('Record the login in the background')
    ip_address = request.client.host
    background_tasks.add_task(record_login, account.id, account.email, ip_address, db)

    print('calling create_access_token()...')
    token = create_access_token(account.email, account.id, timedelta(hours=12))
    response = Response()
    print('response.set_cookie(...')

    print('<--- COOKIE_DOMAIN --->', os.getenv("COOKIE_DOMAIN"))

    response.set_cookie(
        key="jwt",
        value=token,
        httponly=True,

        expires=60*30*24,
        secure=True,
        samesite="None",
        domain=os.getenv("COOKIE_DOMAIN"),
        path="/"
    ) 
    return response


@router.get('/validate-token')
async def validate_token(request: Request, authorization: str = Header(...)):
    try:
        token = authorization.split(" ")[1] # Extract the token from the 'Bearer' scheme
        decoded_token = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return {'access_token': authorization, 'token_type': 'bearer'}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    
@router.delete("/log-out")
@limiter.limit("5/minute")
def logout(request: Request, response: Response):
    response.delete_cookie(
        key="jwt",
        domain=os.getenv("COOKIE_DOMAIN"),
        path="/"
    )
    return {"message": "Logged out successfully"}

@router.post("/request-password-reset")
def request_reset_password(background_tasks: BackgroundTasks, request_body: RequestPasswordResetBody, db: db_dependency):
    try:
        account = db.query(Account).filter(Account.email == request_body.email).first()
        if not account:
            raise "Account not found"

        reset_token: str = str(uuid.uuid4())
        account.reset_token = reset_token
        db.commit()
        
        send_reset_password_link_email_ses(account.id, account.email, reset_token)
    except Exception as e:
        print(e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
@router.post("/reset-password")
def reset_password(background_tasks: BackgroundTasks, request_body: PasswordResetBody, db: db_dependency):
    try:
        account = db.query(Account).filter(
            Account.id == request_body.accountId,
            Account.reset_token == request_body.resetToken
        ).first()
        if not account:
            raise "Account not found"

        hashed_password = bcrypt_context.hash(request_body.newPassword)
        account.hashed_password = hashed_password
        account.reset_token = None

        db.commit()

        # background_tasks.add_task(send_password_reset_email, account.email, reset_token)
        send_password_has_been_reset_email_ses(account.email)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

@router.get("/check-cookies")
def check_cookies(request: Request):
    cookies = request.cookies
    print("Received cookies:", cookies)
    return {"cookies": cookies}