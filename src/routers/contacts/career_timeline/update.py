"""
Update a career timeline entry.
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, auth_dependency
from src.db.models import Contact, CareerTimeline, Account
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..models import UpdateCareerTimelineRequest, CareerTimelineResponse
from src.utils.errors import handle_db_error
from src.services.crm_vector_service import upsert_career_timeline_vector, extract_token

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


@router.put("/{entry_id}", response_model=CareerTimelineResponse)
@limiter.limit("60/minute")
async def update_career_timeline_entry(
    contact_id: int,
    entry_id: int,
    request_body: UpdateCareerTimelineRequest,
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

        entry = db.query(CareerTimeline).filter(
            CareerTimeline.id == entry_id,
            CareerTimeline.contact_id == contact_id,
            CareerTimeline.account_id == account_id,
        ).first()

        if not entry:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Career timeline entry not found")

        if request_body.title is not None:
            if not request_body.title.strip():
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Title cannot be empty")
            entry.title = request_body.title.strip()

        if request_body.description is not None:
            entry.description = request_body.description.strip() or None

        if request_body.start_date is not None:
            entry.start_date = request_body.start_date

        if request_body.end_date is not None:
            entry.end_date = request_body.end_date

        effective_start = request_body.start_date if request_body.start_date is not None else entry.start_date
        effective_end = request_body.end_date if request_body.end_date is not None else entry.end_date
        if effective_end and effective_end < effective_start:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="End date cannot be before start date")

        db.commit()
        db.refresh(entry)

        try:
            token = extract_token(request)
            await upsert_career_timeline_vector(
                token=token,
                entry_id=entry.id,
                account_id=account_id,
                contact_id=contact_id,
                contact_name=contact.name,
                contact_email=contact.email,
                title=entry.title,
                description=entry.description,
                start_date=entry.start_date,
                end_date=entry.end_date,
            )
        except Exception as vec_err:
            print(f"[UPDATE CAREER TIMELINE] Warning: vector upsert failed: {vec_err}")

        return entry

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[UPDATE CAREER TIMELINE]")
