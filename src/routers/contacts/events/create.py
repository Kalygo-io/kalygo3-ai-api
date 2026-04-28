"""
Create a contact event endpoint.
"""
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, auth_dependency
from src.db.models import Contact, ContactEvent, Account

from ..models import CreateContactEventRequest, ContactEventResponse
from src.utils.errors import handle_db_error
from src.services.crm_vector_service import upsert_contact_event_vector, extract_token
from src.rate_limit import limiter

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/", status_code=status.HTTP_201_CREATED, response_model=ContactEventResponse)
@limiter.limit("60/minute")
async def create_contact_event(
    contact_id: int,
    request_body: CreateContactEventRequest,
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
            logger.warning("[CREATE CONTACT EVENT] vector upsert failed: %s", vec_err)

        return event

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[CREATE CONTACT EVENT]")
