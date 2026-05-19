"""
Update deal endpoint.
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, auth_dependency
from src.db.models import Deal, Contact, Account, DEAL_STAGES

from .models import UpdateDealRequest, DealResponse
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

router = APIRouter()


@router.put("/{deal_id}", response_model=DealResponse)
@limiter.limit("30/minute")
async def update_deal(
    deal_id: int,
    request_body: UpdateDealRequest,
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

        if request_body.title is not None:
            if not request_body.title.strip():
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Deal title cannot be empty")
            deal.title = request_body.title.strip()

        if request_body.description is not None:
            deal.description = request_body.description.strip() or None

        if request_body.amount is not None:
            if request_body.amount < 0:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Amount cannot be negative")
            deal.amount = request_body.amount

        if request_body.currency is not None:
            deal.currency = request_body.currency.strip().upper() or 'USD'

        if request_body.stage is not None:
            stage = request_body.stage.strip().lower()
            if stage not in DEAL_STAGES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid stage '{stage}'. Must be one of: {', '.join(DEAL_STAGES)}",
                )
            deal.stage = stage

        if request_body.expected_close_date is not None:
            deal.expected_close_date = request_body.expected_close_date

        if request_body.closed_at is not None:
            deal.closed_at = request_body.closed_at

        # Contact (re)link / unlink. We use model_fields_set so the three
        # cases are distinguishable:
        #   - field omitted        -> leave the link unchanged
        #   - contact_id: null     -> unlink (account-level deal)
        #   - contact_id: <int>    -> link to that contact (validated)
        if 'contact_id' in request_body.model_fields_set:
            if request_body.contact_id is None:
                deal.contact_id = None
            else:
                contact = db.query(Contact).filter(
                    Contact.id == request_body.contact_id,
                    Contact.account_id == account_id,
                ).first()
                if not contact:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")
                deal.contact_id = request_body.contact_id

        db.commit()
        db.refresh(deal)

        return deal

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[UPDATE DEAL]")
