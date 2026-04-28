from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from src.deps import db_dependency, auth_dependency
from src.db.models import PendingToolApproval
from .models import RejectToolApprovalResponse
from src.rate_limit import limiter

router = APIRouter()

@router.post("/{approval_id}/reject", response_model=RejectToolApprovalResponse)
@limiter.limit("60/minute")
async def reject_tool_approval(
    approval_id: int,
    db: db_dependency,
    auth: auth_dependency,
    request: Request,
):
    """Reject a pending tool action — no execution occurs."""
    account_id = int(auth["id"]) if isinstance(auth["id"], str) else auth["id"]
    now = datetime.now(timezone.utc)

    approval = db.query(PendingToolApproval).filter(
        PendingToolApproval.id == approval_id,
        PendingToolApproval.account_id == account_id,
    ).first()

    if not approval:
        raise HTTPException(status_code=404, detail="Tool approval request not found")

    if approval.status != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"Cannot reject a request with status '{approval.status}'",
        )

    if approval.expires_at < now:
        approval.status = "expired"
        db.commit()
        raise HTTPException(status_code=410, detail="This approval request has already expired")

    approval.status = "rejected"
    db.commit()

    return RejectToolApprovalResponse(
        id=approval.id,
        status="rejected",
        message="Tool action rejected",
    )
