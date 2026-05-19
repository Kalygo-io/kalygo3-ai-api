"""
List deals endpoint (account-scoped, server-side paginated).
"""
from fastapi import APIRouter, HTTPException, status, Request, Query
from src.deps import db_dependency, auth_dependency
from src.db.models import Deal, Account

from .models import DealListResponse
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

router = APIRouter()


@router.get("/", response_model=DealListResponse)
@limiter.limit("60/minute")
async def list_deals(
    db: db_dependency,
    auth: auth_dependency,
    request: Request,
    contact_id: int | None = Query(default=None, description="Filter to deals for this contact"),
    stage: str | None = Query(default=None, description="Filter by pipeline stage"),
    search: str | None = Query(default=None, description="Full-text over title/description"),
    limit: int = Query(50, ge=1, le=500, description="Number of deals to return"),
    offset: int = Query(0, ge=0, description="Number of deals to skip"),
):
    """
    List deals for the authenticated account.

    Optional filters: ?contact_id=, ?stage=, and full-text ?search= over
    title/description. Returns a paginated envelope
    ({deals, total, limit, offset, has_more}).
    """
    try:
        account_id = int(auth['id']) if isinstance(auth['id'], str) else auth['id']
        account = db.query(Account).filter(Account.id == account_id).first()

        if not account:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

        query = db.query(Deal).filter(Deal.account_id == account_id)

        if contact_id is not None:
            query = query.filter(Deal.contact_id == contact_id)

        if stage:
            query = query.filter(Deal.stage == stage.strip().lower())

        if search:
            term = f"%{search.lower()}%"
            from sqlalchemy import func as sqlfunc
            query = query.filter(
                sqlfunc.lower(Deal.title).like(term)
                | sqlfunc.lower(Deal.description).like(term)
            )

        total = query.count()
        deals = (
            query.order_by(Deal.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        return DealListResponse(
            deals=deals,
            total=total,
            limit=limit,
            offset=offset,
            has_more=(offset + limit) < total,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise handle_db_error(e, "[LIST DEALS]")
