"""
Get single contact endpoint (includes full event timeline).
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, auth_dependency, account_id_from_claims, ensure_account
from src.db.models import Contact

from .models import ContactResponse
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

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
        account_id = account_id_from_claims(auth)
        account = ensure_account(db, account_id)

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
