"""
Update contact endpoint.
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, auth_dependency
from src.db.models import Contact, Account
from slowapi import Limiter
from slowapi.util import get_remote_address

from .models import UpdateContactRequest, ContactSummaryResponse
from src.utils.errors import handle_db_error

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


@router.put("/{contact_id}", response_model=ContactSummaryResponse)
@limiter.limit("30/minute")
async def update_contact(
    contact_id: int,
    request_body: UpdateContactRequest,
    db: db_dependency,
    auth: auth_dependency,
    request: Request,
):
    try:
        account_id = int(auth['id']) if isinstance(auth['id'], str) else auth['id']
        account = db.query(Account).filter(Account.id == account_id).first()

        if not account:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

        contact = db.query(Contact).filter(
            Contact.id == contact_id,
            Contact.account_id == account_id,
        ).first()

        if not contact:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")

        if request_body.first_name is not None:
            if not request_body.first_name.strip():
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Contact first name cannot be empty")
            contact.first_name = request_body.first_name.strip()

        if request_body.last_name is not None:
            contact.last_name = request_body.last_name.strip() or None

        if request_body.email is not None:
            if not request_body.email.strip():
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Contact email cannot be empty")
            contact.email = request_body.email.strip().lower()

        if request_body.phone is not None:
            contact.phone = request_body.phone or None

        if request_body.company is not None:
            contact.company = request_body.company or None

        if request_body.title is not None:
            contact.title = request_body.title or None

        if request_body.source is not None:
            contact.source = request_body.source or None

        if request_body.status is not None:
            contact.status = request_body.status or None

        if request_body.notes is not None:
            contact.notes = request_body.notes or None

        db.commit()
        db.refresh(contact)

        return contact

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[UPDATE CONTACT]")
