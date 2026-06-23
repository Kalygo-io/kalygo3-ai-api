"""
Get single contact list endpoint (includes full member list).
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, auth_dependency, account_id_from_claims, ensure_account
from src.db.models import ContactList

from .models import ContactListResponse
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

router = APIRouter()

@router.get("/{list_id}", response_model=ContactListResponse)
@limiter.limit("60/minute")
async def get_contact_list(
    list_id: int,
    db: db_dependency,
    auth: auth_dependency,
    request: Request,
):
    try:
        account_id = account_id_from_claims(auth)
        account = ensure_account(db, account_id)

        contact_list = db.query(ContactList).filter(
            ContactList.id == list_id,
            ContactList.account_id == account_id,
        ).first()

        if not contact_list:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact list not found")

        return contact_list

    except HTTPException:
        raise
    except Exception as e:
        raise handle_db_error(e, "[GET CONTACT LIST]")
