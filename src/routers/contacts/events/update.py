"""
Update a contact event endpoint.
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency
from src.db.models import Contact, ContactEvent, Account
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..models import UpdateContactEventRequest, ContactEventResponse

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


@router.put("/{event_id}", response_model=ContactEventResponse)
@limiter.limit("30/minute")
async def update_contact_event(
    contact_id: int,
    event_id: int,
    request_body: UpdateContactEventRequest,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request,
):
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

        event = db.query(ContactEvent).filter(
            ContactEvent.id == event_id,
            ContactEvent.contact_id == contact_id,
        ).first()

        if not event:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

        if request_body.event_type is not None:
            if not request_body.event_type.strip():
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="event_type cannot be empty")
            event.event_type = request_body.event_type.strip()

        if request_body.title is not None:
            if not request_body.title.strip():
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Event title cannot be empty")
            event.title = request_body.title.strip()

        if request_body.description is not None:
            event.description = request_body.description or None

        if request_body.occurred_at is not None:
            event.occurred_at = request_body.occurred_at

        db.commit()
        db.refresh(event)

        return event

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"[UPDATE CONTACT EVENT] Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update contact event: {str(e)}",
        )
