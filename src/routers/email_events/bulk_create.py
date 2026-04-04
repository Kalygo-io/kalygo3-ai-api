"""
Bulk-create email events endpoint — for ingesting webhook payloads.
"""
from typing import List
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, auth_dependency
from src.db.models import EmailEvent
from slowapi import Limiter
from slowapi.util import get_remote_address

from .models import BulkCreateEmailEventsRequest, EmailEventResponse
from src.utils.errors import handle_db_error

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


@router.post("/bulk", status_code=status.HTTP_201_CREATED, response_model=List[EmailEventResponse])
@limiter.limit("30/minute")
async def bulk_create_email_events(
    request_body: BulkCreateEmailEventsRequest,
    db: db_dependency,
    auth: auth_dependency,
    request: Request,
):
    """
    Record multiple email events in a single request.
    Useful for ingesting batched SNS/SES webhook notifications.
    All events are written atomically — if any fail the whole batch is rolled back.
    """
    try:
        account_id = int(auth['id']) if isinstance(auth['id'], str) else auth['id']

        if not request_body.events:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="events list cannot be empty")

        events = [
            EmailEvent(
                account_id=account_id,
                email_address=e.email_address.strip().lower(),
                event_type=e.event_type,
                tool_approval_id=e.tool_approval_id,
                campaign_id=e.campaign_id,
                contact_id=e.contact_id,
                provider=e.provider,
                provider_message_id=e.provider_message_id,
                event_metadata=e.event_metadata,
            )
            for e in request_body.events
        ]

        db.add_all(events)
        db.commit()

        for ev in events:
            db.refresh(ev)

        return events

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[BULK CREATE EMAIL EVENTS]")
