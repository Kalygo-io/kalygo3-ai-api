"""
List contact events endpoint.
"""
from typing import List
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency
from src.db.models import Contact, ContactEvent, Account
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..models import ContactEventResponse

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


@router.get("/", response_model=List[ContactEventResponse])
@limiter.limit("60/minute")
async def list_contact_events(
    contact_id: int,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request,
):
    """Return events for a contact ordered most-recent first."""
    try:
        account_id = int(jwt['id']) if isinstance(jwt['id'], str) else jwt['id']
        account = db.query(Account).filter(Account.id == account_id).first()

        if not account:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

        contact = db.query(Contact).filter(
            Contact.id == contact_id,
            Contact.account_id == account_id,
        ).first()

        if not contact:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")

        events = (
            db.query(ContactEvent)
            .filter(ContactEvent.contact_id == contact_id)
            .order_by(ContactEvent.occurred_at.desc())
            .all()
        )

        return events

    except HTTPException:
        raise
    except Exception as e:
        print(f"[LIST CONTACT EVENTS] Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list contact events: {str(e)}",
        )
