"""
Create email event endpoint.
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, auth_dependency
from src.db.models import EmailEvent
from slowapi import Limiter
from slowapi.util import get_remote_address

from .models import CreateEmailEventRequest, EmailEventResponse
from src.utils.errors import handle_db_error

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=EmailEventResponse)
@limiter.limit("120/minute")
async def create_email_event(
    request_body: CreateEmailEventRequest,
    db: db_dependency,
    auth: auth_dependency,
    request: Request,
):
    """Record a single email event."""
    try:
        account_id = int(auth['id']) if isinstance(auth['id'], str) else auth['id']

        event = EmailEvent(
            account_id=account_id,
            email_address=request_body.email_address.strip().lower(),
            event_type=request_body.event_type,
            tool_approval_id=request_body.tool_approval_id,
            campaign_id=request_body.campaign_id,
            contact_id=request_body.contact_id,
            provider=request_body.provider,
            provider_message_id=request_body.provider_message_id,
            event_metadata=request_body.event_metadata,
        )

        db.add(event)
        db.commit()
        db.refresh(event)

        return event

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[CREATE EMAIL EVENT]")
