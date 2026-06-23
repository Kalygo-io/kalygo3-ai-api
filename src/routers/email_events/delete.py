"""
Delete email event endpoint.
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, auth_dependency, account_id_from_claims
from src.db.models import EmailEvent
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

router = APIRouter()

@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("30/minute")
async def delete_email_event(
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

        db.delete(event)
        db.commit()

        return None

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[DELETE EMAIL EVENT]")
