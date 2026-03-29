"""
Create contact endpoint.
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, auth_dependency
from src.db.models import Contact, Account
from slowapi import Limiter
from slowapi.util import get_remote_address

from .models import CreateContactRequest, ContactSummaryResponse
from src.utils.errors import handle_db_error

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=ContactSummaryResponse)
@limiter.limit("30/minute")
async def create_contact(
    request_body: CreateContactRequest,
    db: db_dependency,
    auth: auth_dependency,
    request: Request,
):
    try:
        account_id = int(auth['id']) if isinstance(auth['id'], str) else auth['id']
        account = db.query(Account).filter(Account.id == account_id).first()

        if not account:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

        if not request_body.first_name or not request_body.first_name.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Contact first name cannot be empty")

        if not request_body.email or not request_body.email.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Contact email cannot be empty")

        contact = Contact(
            account_id=account_id,
            first_name=request_body.first_name.strip(),
            last_name=request_body.last_name.strip() if request_body.last_name else None,
            email=request_body.email.strip().lower(),
            phone=request_body.phone,
            company=request_body.company,
            title=request_body.title,
            source=request_body.source,
            status=request_body.status,
            notes=request_body.notes,
        )

        db.add(contact)
        db.commit()
        db.refresh(contact)

        return contact

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[CREATE CONTACT]")
