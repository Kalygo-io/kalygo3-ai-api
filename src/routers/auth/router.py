from datetime import timedelta, datetime, timezone
import hashlib
import random
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Header, Response, BackgroundTasks, Request
from pydantic import BaseModel
from jose import jwt
from dotenv import load_dotenv
import os
from src.db.models import Account, UsageCredits
from src.routers.auth.background_tasks import record_login
from src.routers.auth.background_tasks.send_reset_password_link_email_ses import send_reset_password_link_email_ses
from src.routers.auth.background_tasks.send_password_has_been_reset_email_ses import send_password_has_been_reset_email_ses
from src.routers.auth.background_tasks.send_login_code_email_ses import send_login_code_email_ses
from src.deps import db_dependency, bcrypt_context, jwt_dependency
from src.clients.stripe_client import create_stripe_customer
import stripe

from slowapi import Limiter
from slowapi.util import get_remote_address
from src.utils.errors import handle_db_error

limiter = Limiter(key_func=get_remote_address)

load_dotenv()

router = APIRouter()

SECRET_KEY = os.getenv("AUTH_SECRET_KEY")
ALGORITHM = os.getenv("AUTH_ALGORITHM")

class AccountCreateRequestBody(BaseModel):
    email: str
    password: str
    newsletter_subscribed: bool = False

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


def _issue_jwt_cookie(response: Response, account: Account) -> Response:
    token = create_access_token(account.email, account.id, timedelta(hours=12))
    response.set_cookie(
        key="jwt",
        value=token,
        httponly=True,
        expires=60 * 30 * 24,
        secure=True,
        samesite="None",
        domain=os.getenv("COOKIE_DOMAIN"),
        path="/",
    )
    return response

def authenticate(email: str, password: str, db):
    print("authenticate...")

    account = db.query(Account).filter(Account.email == email).first()
    if not account:
        return False
    
    if not bcrypt_context.verify(password, account.hashed_password):
        return False
    return account

def create_access_token(email: str, user_id: int, expires_delta: timedelta):
    encode = {'sub': email, 'id': user_id}
    expires = datetime.now(timezone.utc) + expires_delta
    encode.update({'exp': expires})
    return jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)

@router.post("/create-account", status_code=status.HTTP_201_CREATED)
async def create_account(db: db_dependency, create_account_request: AccountCreateRequestBody, request: Request):
    # ============================================================
    # TEMPORARY DEVELOPMENT LIMIT: Maximum 50 accounts
    # This is a hard-coded limit during early development stages.
    # Remove this check before production deployment.
    # ============================================================
    account_count = db.query(Account).count()
    if account_count >= 50:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account creation is currently limited. Maximum number of accounts reached."
        )
    # ============================================================
    
    stripe_customer_id = None
    try:
        # Create Stripe customer first
        try:
            stripe_customer_id = create_stripe_customer(create_account_request.email)
            print(f"Created Stripe customer: {stripe_customer_id} for email: {create_account_request.email}")
        except stripe.error.StripeError as e:
            print(f"Failed to create Stripe customer: {str(e)}")
            # Continue with account creation even if Stripe fails
            # The stripe_id will remain None
        except Exception as e:
            print(f"Unexpected error creating Stripe customer: {str(e)}")
            # Continue with account creation
        
        # Create account with Stripe customer ID
        hashed_password = bcrypt_context.hash(create_account_request.password)
        create_account_model = Account(
            email=create_account_request.email,
            hashed_password=hashed_password,
            stripe_customer_id=stripe_customer_id,
            newsletter_subscribed=create_account_request.newsletter_subscribed
        )
        db.add(create_account_model)
        db.commit()
        db.refresh(create_account_model)
        
        # Create initial usage credits for new account ($0.50)
        try:
            usage_credits = UsageCredits(
                account_id=create_account_model.id,
                amount=1.00 # $1.00
            )
            db.add(usage_credits)
            db.commit()
            print(f"Created initial usage credits: $1.00 for account {create_account_model.id}")
        except Exception as e:
            print(f"Failed to create usage credits: {str(e)}")
            db.rollback()
            # Don't fail account creation if credits creation fails, but log the error
        
        print(f"Account created successfully: {create_account_model.id} with Stripe ID: {stripe_customer_id}")
        
    except Exception as e:
        db.rollback()
        print(f'create_user error: {e}')
        raise handle_db_error(e, "[OPERATION]")
    

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
        raise handle_db_error(e, "[OPERATION]")

@router.get('/me', response_model=CurrentUserResponse)
async def get_current_user_info(current_user: jwt_dependency, request: Request):
    """
    Get the current user's email from the JWT token.
    """
    print(f'--- /me endpoint called ---')
    print(f'--- current_user: {current_user} ---')
    print(f'--- cookies: {request.cookies} ---')
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
            # Auto-create account (dev cap still applies)
            account_count = db.query(Account).count()
            if account_count >= 50:
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

        code = str(random.randint(100000, 999999))
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
    background_tasks.add_task(record_login, account.id, account.email, ip_address, db)

    response = Response()
    return _issue_jwt_cookie(response, account)


@router.get("/check-cookies")
def check_cookies(request: Request):
    cookies = request.cookies
    print("Received cookies:", cookies)
    return {"cookies": cookies}

