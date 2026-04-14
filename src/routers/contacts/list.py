"""
List contacts endpoint.
"""
from typing import List
from fastapi import APIRouter, HTTPException, status, Request, Query
from src.deps import db_dependency, auth_dependency
from src.db.models import Contact, Account
from slowapi import Limiter
from slowapi.util import get_remote_address

from .models import ContactSummaryResponse
from src.utils.errors import handle_db_error

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


@router.get("/", response_model=List[ContactSummaryResponse])
@limiter.limit("60/minute")
async def list_contacts(
    db: db_dependency,
    auth: auth_dependency,
    request: Request,
    status_filter: str | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None),
):
    """
    List all contacts for the authenticated user.

    Supports optional filtering by ?status= and full-text ?search= over
    name, email, and company.
    """
    try:
        account_id = int(auth['id']) if isinstance(auth['id'], str) else auth['id']
        account = db.query(Account).filter(Account.id == account_id).first()

        if not account:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

        query = db.query(Contact).filter(Contact.account_id == account_id)

        if status_filter:
            query = query.filter(Contact.status == status_filter)

        if search:
            term = f"%{search.lower()}%"
            from sqlalchemy import func as sqlfunc
            query = query.filter(
                sqlfunc.lower(Contact.first_name).like(term)
                | sqlfunc.lower(Contact.middle_name).like(term)
                | sqlfunc.lower(Contact.last_name).like(term)
                | sqlfunc.lower(Contact.email).like(term)
            )

        contacts = query.order_by(Contact.updated_at.desc()).all()

        return contacts

    except HTTPException:
        raise
    except Exception as e:
        raise handle_db_error(e, "[LIST CONTACTS]")
