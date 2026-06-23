"""
List contacts endpoint.
"""
from fastapi import APIRouter, HTTPException, status, Request, Query
from src.deps import db_dependency, auth_dependency, account_id_from_claims, ensure_account
from src.db.models import Contact

from .models import ContactListResponse
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

router = APIRouter()

@router.get("/", response_model=ContactListResponse)
@limiter.limit("60/minute")
async def list_contacts(
    db: db_dependency,
    auth: auth_dependency,
    request: Request,
    status_filter: str | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None),
    limit: int = Query(50, ge=1, le=500, description="Number of contacts to return"),
    offset: int = Query(0, ge=0, description="Number of contacts to skip"),
):
    """
    List contacts for the authenticated user (server-side paginated).

    Supports optional filtering by ?status= and full-text ?search= over
    first/middle/last name and all emails (default + alternates). Returns
    a paginated envelope
    ({contacts, total, limit, offset, has_more}).
    """
    try:
        account_id = account_id_from_claims(auth)
        account = ensure_account(db, account_id)

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
                | sqlfunc.lower(Contact.alt_email_1).like(term)
                | sqlfunc.lower(Contact.alt_email_2).like(term)
            )

        # Total before pagination, then the requested slice.
        total = query.count()
        contacts = (
            query.order_by(Contact.updated_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        return ContactListResponse(
            contacts=contacts,
            total=total,
            limit=limit,
            offset=offset,
            has_more=(offset + limit) < total,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise handle_db_error(e, "[LIST CONTACTS]")
