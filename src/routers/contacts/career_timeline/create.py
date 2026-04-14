"""
Create a career timeline entry for a contact.
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, auth_dependency
from src.db.models import Contact, CareerTimeline, Account
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..models import CreateCareerTimelineRequest, CareerTimelineResponse
from src.utils.errors import handle_db_error
from src.services.crm_vector_service import upsert_career_timeline_vector, extract_token

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=CareerTimelineResponse)
@limiter.limit("60/minute")
async def create_career_timeline_entry(
    contact_id: int,
    request_body: CreateCareerTimelineRequest,
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

        if not request_body.title or not request_body.title.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Title cannot be empty")

        if request_body.end_date and request_body.end_date < request_body.start_date:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="End date cannot be before start date")

        entry = CareerTimeline(
            contact_id=contact_id,
            account_id=account_id,
            title=request_body.title.strip(),
            description=request_body.description.strip() if request_body.description else None,
            start_date=request_body.start_date,
            end_date=request_body.end_date,
        )

        db.add(entry)
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
            print(f"[CREATE CAREER TIMELINE] Warning: vector upsert failed: {vec_err}")

        return entry

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[CREATE CAREER TIMELINE]")
