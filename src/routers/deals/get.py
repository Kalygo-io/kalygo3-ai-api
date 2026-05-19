"""
Get single deal endpoint.
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, auth_dependency
from src.db.models import Deal, Account

from .models import DealResponse
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

router = APIRouter()


@router.get("/{deal_id}", response_model=DealResponse)
@limiter.limit("60/minute")
async def get_deal(
    deal_id: int,
    db: db_dependency,
    auth: auth_dependency,
    request: Request,
):
    try:
        account_id = int(auth['id']) if isinstance(auth['id'], str) else auth['id']
        account = db.query(Account).filter(Account.id == account_id).first()

        if not account:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

        deal = db.query(Deal).filter(
            Deal.id == deal_id,
            Deal.account_id == account_id,
        ).first()

        if not deal:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")

        return deal

    except HTTPException:
        raise
    except Exception as e:
        raise handle_db_error(e, "[GET DEAL]")
