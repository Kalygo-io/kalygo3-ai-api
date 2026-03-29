"""
Get single contact endpoint (includes full event timeline).
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, auth_dependency
from src.db.models import Contact, Account
from slowapi import Limiter
from slowapi.util import get_remote_address

from .models import ContactResponse
from src.utils.errors import handle_db_error

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


@router.get("/{contact_id}", response_model=ContactResponse)
@limiter.limit("60/minute")
async def get_contact(
    contact_id: int,
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

        return contact

    except HTTPException:
        raise
    except Exception as e:
        raise handle_db_error(e, "[GET CONTACT]")
