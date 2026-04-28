"""
Update email event endpoint.
Only event_metadata is mutable — event_type, provider, and timestamps are immutable.
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, auth_dependency
from src.db.models import EmailEvent

from .models import UpdateEmailEventRequest, EmailEventResponse
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

router = APIRouter()

@router.patch("/{event_id}", response_model=EmailEventResponse)
@limiter.limit("30/minute")
async def update_email_event(
    event_id: int,
    request_body: UpdateEmailEventRequest,
    db: db_dependency,
    auth: auth_dependency,
    request: Request,
):
    """
    Update the event_metadata of an email event.
    Use this to enrich an event with additional context after the fact
    (e.g. attaching a bounce subtype received from a delayed webhook).
    """
    try:
        account_id = int(auth['id']) if isinstance(auth['id'], str) else auth['id']

        event = db.query(EmailEvent).filter(
            EmailEvent.id == event_id,
            EmailEvent.account_id == account_id,
        ).first()

        if not event:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email event not found")

        if request_body.event_metadata is not None:
            event.event_metadata = request_body.event_metadata

        db.commit()
        db.refresh(event)

        return event

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[UPDATE EMAIL EVENT]")
