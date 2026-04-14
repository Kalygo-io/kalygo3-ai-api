"""
Delete a career timeline entry.
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, auth_dependency
from src.db.models import Contact, CareerTimeline, Account
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.utils.errors import handle_db_error

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("60/minute")
async def delete_career_timeline_entry(
    contact_id: int,
    entry_id: int,
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

        entry = db.query(CareerTimeline).filter(
            CareerTimeline.id == entry_id,
            CareerTimeline.contact_id == contact_id,
            CareerTimeline.account_id == account_id,
        ).first()

        if not entry:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Career timeline entry not found")

        db.delete(entry)
        db.commit()

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[DELETE CAREER TIMELINE]")
