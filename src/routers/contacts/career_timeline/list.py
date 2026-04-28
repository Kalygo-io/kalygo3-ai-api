"""
List career timeline entries for a contact.
"""
from typing import List
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, auth_dependency
from src.db.models import Contact, CareerTimeline, Account

from ..models import CareerTimelineResponse
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

router = APIRouter()

@router.get("/", response_model=List[CareerTimelineResponse])
@limiter.limit("60/minute")
async def list_career_timeline(
    contact_id: int,
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

        entries = (
            db.query(CareerTimeline)
            .filter(
                CareerTimeline.contact_id == contact_id,
                CareerTimeline.account_id == account_id,
            )
            .order_by(CareerTimeline.start_date.desc())
            .all()
        )

        return entries

    except HTTPException:
        raise
    except Exception as e:
        raise handle_db_error(e, "[LIST CAREER TIMELINE]")
