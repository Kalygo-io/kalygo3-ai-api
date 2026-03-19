"""
Create a contact event endpoint.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency
from src.db.models import Contact, ContactEvent, Account
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..models import CreateContactEventRequest, ContactEventResponse

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=ContactEventResponse)
@limiter.limit("60/minute")
async def create_contact_event(
    contact_id: int,
    request_body: CreateContactEventRequest,
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

        if not request_body.event_type or not request_body.event_type.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="event_type cannot be empty")

        if not request_body.title or not request_body.title.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Event title cannot be empty")

        occurred_at = request_body.occurred_at or datetime.now(timezone.utc)

        event = ContactEvent(
            contact_id=contact_id,
            account_id=account_id,
            event_type=request_body.event_type.strip(),
            title=request_body.title.strip(),
            description=request_body.description,
            occurred_at=occurred_at,
        )

        db.add(event)
        db.commit()
        db.refresh(event)

        return event

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"[CREATE CONTACT EVENT] Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create contact event: {str(e)}",
        )
