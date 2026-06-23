"""
Get single email event endpoint.
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, auth_dependency, account_id_from_claims
from src.db.models import EmailEvent

from .models import EmailEventResponse
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

router = APIRouter()

@router.get("/{event_id}", response_model=EmailEventResponse)
@limiter.limit("60/minute")
async def get_email_event(
    event_id: int,
    db: db_dependency,
    auth: auth_dependency,
    request: Request,
):
    try:
        account_id = account_id_from_claims(auth)

        event = db.query(EmailEvent).filter(
            EmailEvent.id == event_id,
            EmailEvent.account_id == account_id,
        ).first()

        if not event:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email event not found")

        return event

    except HTTPException:
        raise
    except Exception as e:
        raise handle_db_error(e, "[GET EMAIL EVENT]")
