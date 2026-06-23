"""
Create deal endpoint.
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, auth_dependency, account_id_from_claims, ensure_account
from src.db.models import Deal, Contact, DEAL_STAGES

from .models import CreateDealRequest, DealResponse
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

router = APIRouter()


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=DealResponse)
@limiter.limit("30/minute")
async def create_deal(
    request_body: CreateDealRequest,
    db: db_dependency,
    auth: auth_dependency,
    request: Request,
):
    try:
        account_id = account_id_from_claims(auth)
        account = ensure_account(db, account_id)

        if not request_body.title or not request_body.title.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Deal title cannot be empty")

        stage = (request_body.stage or 'lead').strip().lower()
        if stage not in DEAL_STAGES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid stage '{stage}'. Must be one of: {', '.join(DEAL_STAGES)}",
            )

        if request_body.amount is not None and request_body.amount < 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Amount cannot be negative")

        # Optional contact link must belong to this account.
        if request_body.contact_id is not None:
            contact = db.query(Contact).filter(
                Contact.id == request_body.contact_id,
                Contact.account_id == account_id,
            ).first()
            if not contact:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")

        currency = (request_body.currency or 'USD').strip().upper() or 'USD'

        deal = Deal(
            account_id=account_id,
            contact_id=request_body.contact_id,
            title=request_body.title.strip(),
            description=request_body.description.strip() if request_body.description else None,
            amount=request_body.amount,
            currency=currency,
            stage=stage,
            expected_close_date=request_body.expected_close_date,
            closed_at=request_body.closed_at,
        )

        db.add(deal)
        db.commit()
        db.refresh(deal)

        return deal

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[CREATE DEAL]")
