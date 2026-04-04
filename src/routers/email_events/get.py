"""
Get single email event endpoint.
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, auth_dependency
from src.db.models import EmailEvent
from slowapi import Limiter
from slowapi.util import get_remote_address

from .models import EmailEventResponse
from src.utils.errors import handle_db_error

limiter = Limiter(key_func=get_remote_address)
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
        account_id = int(auth['id']) if isinstance(auth['id'], str) else auth['id']

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
