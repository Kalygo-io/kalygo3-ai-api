"""
Create contact endpoint.
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, auth_dependency, account_id_from_claims, ensure_account
from src.db.models import Contact

from .models import CreateContactRequest, ContactSummaryResponse
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

router = APIRouter()

@router.post("/", status_code=status.HTTP_201_CREATED, response_model=ContactSummaryResponse)
@limiter.limit("30/minute")
async def create_contact(
    request_body: CreateContactRequest,
    db: db_dependency,
    auth: auth_dependency,
    request: Request,
):
    try:
        account_id = account_id_from_claims(auth)
        account = ensure_account(db, account_id)

        if not request_body.first_name or not request_body.first_name.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Contact first name cannot be empty")

        if not request_body.email or not request_body.email.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Contact email cannot be empty")

        def _norm_email(value: str | None) -> str | None:
            """Normalize an optional email the same way the primary is: trimmed
            + lowercased, with blank coerced to NULL."""
            if not value or not value.strip():
                return None
            return value.strip().lower()

        def _norm_url(value: str | None) -> str | None:
            """Trim an optional URL; coerce blank to NULL. Case is preserved
            since URL paths can be case-sensitive."""
            if not value or not value.strip():
                return None
            return value.strip()

        contact = Contact(
            account_id=account_id,
            first_name=request_body.first_name.strip(),
            middle_name=request_body.middle_name.strip() if request_body.middle_name else None,
            last_name=request_body.last_name.strip() if request_body.last_name else None,
            email=request_body.email.strip().lower(),
            alt_email_1=_norm_email(request_body.alt_email_1),
            alt_email_2=_norm_email(request_body.alt_email_2),
            phone=request_body.phone,
            source=request_body.source,
            linkedin_url=_norm_url(request_body.linkedin_url),
            instagram_url=_norm_url(request_body.instagram_url),
            youtube_url=_norm_url(request_body.youtube_url),
            x_url=_norm_url(request_body.x_url),
        )

        db.add(contact)
        db.commit()
        db.refresh(contact)

        return contact

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[CREATE CONTACT]")
