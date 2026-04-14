"""
Update a contact event endpoint.
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, auth_dependency
from src.db.models import Contact, ContactEvent, Account
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..models import UpdateContactEventRequest, ContactEventResponse
from src.utils.errors import handle_db_error
from src.services.crm_vector_service import upsert_contact_event_vector, extract_token

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


@router.put("/{event_id}", response_model=ContactEventResponse)
@limiter.limit("30/minute")
async def update_contact_event(
    contact_id: int,
    event_id: int,
    request_body: UpdateContactEventRequest,
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

        try:
            token = extract_token(request)
            await upsert_contact_event_vector(
                token=token,
                event_id=event.id,
                account_id=account_id,
                contact_id=contact_id,
                contact_name=contact.name,
                contact_email=contact.email,
                event_type=event.event_type,
                title=event.title,
                description=event.description,
                occurred_at=event.occurred_at,
            )
        except Exception as vec_err:
            print(f"[UPDATE CONTACT EVENT] Warning: vector upsert failed: {vec_err}")

        return event

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[UPDATE CONTACT EVENT]")
