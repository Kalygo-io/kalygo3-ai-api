"""
Create email event endpoint.
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, auth_dependency, account_id_from_claims
from src.db.models import EmailEvent

from .models import CreateEmailEventRequest, EmailEventResponse
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

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
        account_id = account_id_from_claims(auth)

        credential_id = request_body.credential_id
        sender_domain = request_body.sender_domain

        if request_body.message_id and (not credential_id or not sender_domain):
            original = db.query(EmailEvent).filter(
                EmailEvent.account_id == account_id,
                EmailEvent.message_id == request_body.message_id,
                EmailEvent.event_type == "send_to_ses",
            ).first()
            if original:
                if not credential_id:
                    credential_id = original.credential_id
                if not sender_domain:
                    sender_domain = original.sender_domain

        event = EmailEvent(
            account_id=account_id,
            primary_recipient=request_body.primary_recipient.strip().lower() if request_body.primary_recipient else None,
            event_type=request_body.event_type,
            tool_approval_id=request_body.tool_approval_id,
            campaign_id=request_body.campaign_id,
            contact_id=request_body.contact_id,
            credential_id=credential_id,
            sender_domain=sender_domain,
            provider=request_body.provider,
            message_id=request_body.message_id,
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
