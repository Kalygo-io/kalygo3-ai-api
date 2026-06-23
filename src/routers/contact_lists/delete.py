"""
Delete contact list endpoint.
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, auth_dependency, account_id_from_claims, ensure_account
from src.db.models import ContactList
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

router = APIRouter()

@router.delete("/{list_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("30/minute")
async def delete_contact_list(
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

        db.delete(contact_list)
        db.commit()

        return None

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[DELETE CONTACT LIST]")
