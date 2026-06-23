from datetime import timedelta, datetime, timezone
import hashlib
import random
import uuid
from fastapi import APIRouter, HTTPException, status, Header, Response, BackgroundTasks, Request
from pydantic import BaseModel
from jose import jwt
import os
from src.db.models import Account, UsageCredits
from src.routers.auth.background_tasks import record_login
from src.routers.auth.background_tasks.send_reset_password_link_email_ses import send_reset_password_link_email_ses
from src.routers.auth.background_tasks.send_password_has_been_reset_email_ses import send_password_has_been_reset_email_ses
from src.routers.auth.background_tasks.send_login_code_email_ses import send_login_code_email_ses
from src.deps import db_dependency, bcrypt_context, jwt_dependency
from src.clients.stripe_client import create_stripe_customer

from src.utils.errors import handle_db_error
from src.rate_limit import limiter

router = APIRouter()

SECRET_KEY = os.getenv("AUTH_SECRET_KEY")
ALGORITHM = os.getenv("AUTH_ALGORITHM")

class RequestPasswordResetBody(BaseModel):
    email: str

class PasswordResetBody(BaseModel):
    accountId: int
    resetToken: str
    newPassword: str

class CurrentUserResponse(BaseModel):
    email: str

class RequestCodeBody(BaseModel):
    email: str

class VerifyCodeBody(BaseModel):
    email: str
    code: str

OTP_TTL_MINUTES = 10

def _hash_otp(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()

def _issue_jwt_cookie(response: Response, token: str) -> Response:
    response.set_cookie(
        key="jwt",
        value=token,
        httponly=True,
        expires=60 * 60 * 24 * 7,
        secure=True,
        samesite="None",
        domain=os.getenv("COOKIE_DOMAIN"),
        path="/",
    )
    return response

def create_access_token(email: str, user_id: int, expires_delta: timedelta):
    encode = {'sub': email, 'id': user_id}
    expires = datetime.now(timezone.utc) + expires_delta
    encode.update({'exp': expires})
    return jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)

@router.get('/validate-token')
async def validate_token(request: Request, authorization: str = Header(...)):
    try:
        token = authorization.split(" ")[1]
        jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return {'access_token': authorization, 'token_type': 'bearer'}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired")
    except Exception as e:
        raise handle_db_error(e, "[OPERATION]")

@router.get('/me', response_model=CurrentUserResponse)
async def get_current_user_info(current_user: jwt_dependency, request: Request):
    return CurrentUserResponse(email=current_user['email'])

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
def request_reset_password(request_body: RequestPasswordResetBody, db: db_dependency):
    try:
        account = db.query(Account).filter(Account.email == request_body.email).first()
        if not account:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

        reset_token: str = str(uuid.uuid4())
        account.reset_token = reset_token
        db.commit()

        send_reset_password_link_email_ses(account.id, account.email, reset_token)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

@router.post("/reset-password")
def reset_password(request_body: PasswordResetBody, db: db_dependency):
    try:
        account = db.query(Account).filter(
            Account.id == request_body.accountId,
            Account.reset_token == request_body.resetToken
        ).first()
        if not account:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

        account.hashed_password = bcrypt_context.hash(request_body.newPassword)
        account.reset_token = None
        db.commit()

        send_password_has_been_reset_email_ses(account.email)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

@router.post("/request-code", status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
async def request_login_code(body: RequestCodeBody, db: db_dependency, request: Request, background_tasks: BackgroundTasks):
    """
    Step 1 of OTP login/signup.
    Creates the account if it doesn't exist, then emails a 6-digit code.
    Always returns 200 to avoid leaking whether the email is registered.
    """
    try:
        account = db.query(Account).filter(Account.email == body.email).first()

        if not account:
            account_count = db.query(Account).count()
            if account_count >= 400:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Account creation is currently limited.",
                )
            stripe_customer_id = None
            try:
                stripe_customer_id = create_stripe_customer(body.email)
            except Exception:
                pass

            account = Account(
                email=body.email,
                stripe_customer_id=stripe_customer_id,
            )
            db.add(account)
            db.flush()

            try:
                usage_credits = UsageCredits(account_id=account.id, amount=1.00)
                db.add(usage_credits)
            except Exception:
                pass

            db.commit()
            db.refresh(account)

        code = str(random.randint(10000000, 99999999))
        account.login_otp = _hash_otp(code)
        account.login_otp_expires_at = datetime.now(timezone.utc) + timedelta(minutes=OTP_TTL_MINUTES)
        db.commit()

        background_tasks.add_task(send_login_code_email_ses, account.email, code)
        return {"detail": "Code sent"}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[REQUEST CODE]")

@router.post("/verify-code")
@limiter.limit("10/minute")
async def verify_login_code(body: VerifyCodeBody, db: db_dependency, request: Request, background_tasks: BackgroundTasks):
    """
    Step 2 of OTP login/signup.
    Validates the 6-digit code and issues a JWT session cookie.
    """
    invalid_exc = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired code")

    account = db.query(Account).filter(Account.email == body.email).first()
    if not account or not account.login_otp or not account.login_otp_expires_at:
        raise invalid_exc

    if datetime.now(timezone.utc) > account.login_otp_expires_at:
        raise invalid_exc

    if account.login_otp != _hash_otp(body.code):
        raise invalid_exc

    account.login_otp = None
    account.login_otp_expires_at = None
    db.commit()

    ip_address = request.client.host
    token = create_access_token(account.email, account.id, timedelta(days=7))
    background_tasks.add_task(record_login, account.id, account.email, ip_address, db, token)

    response = Response()
    return _issue_jwt_cookie(response, token)

