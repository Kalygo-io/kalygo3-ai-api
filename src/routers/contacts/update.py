"""
Update contact endpoint.
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, auth_dependency
from src.db.models import Contact, Account

from .models import UpdateContactRequest, ContactSummaryResponse
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

router = APIRouter()

@router.put("/{contact_id}", response_model=ContactSummaryResponse)
@limiter.limit("30/minute")
async def update_contact(
    contact_id: int,
    request_body: UpdateContactRequest,
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

        if request_body.first_name is not None:
            if not request_body.first_name.strip():
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Contact first name cannot be empty")
            contact.first_name = request_body.first_name.strip()

        if request_body.middle_name is not None:
            contact.middle_name = request_body.middle_name.strip() or None

        if request_body.last_name is not None:
            contact.last_name = request_body.last_name.strip() or None

        if request_body.email is not None:
            if not request_body.email.strip():
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Contact email cannot be empty")
            contact.email = request_body.email.strip().lower()

        # Alternate emails are optional: a sent value is trimmed + lowercased
        # (matching the primary), and a blank clears the field.
        if request_body.alt_email_1 is not None:
            contact.alt_email_1 = request_body.alt_email_1.strip().lower() or None

        if request_body.alt_email_2 is not None:
            contact.alt_email_2 = request_body.alt_email_2.strip().lower() or None

        if request_body.phone is not None:
            contact.phone = request_body.phone or None

        if request_body.source is not None:
            contact.source = request_body.source or None

        # Social profiles: a sent value is trimmed, and a blank clears the
        # field (mirroring how phone is handled).
        if request_body.linkedin_url is not None:
            contact.linkedin_url = request_body.linkedin_url.strip() or None

        if request_body.instagram_url is not None:
            contact.instagram_url = request_body.instagram_url.strip() or None

        if request_body.youtube_url is not None:
            contact.youtube_url = request_body.youtube_url.strip() or None

        if request_body.x_url is not None:
            contact.x_url = request_body.x_url.strip() or None

        db.commit()
        db.refresh(contact)

        return contact

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[UPDATE CONTACT]")
