from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, HTTPException, Request
from src.deps import db_dependency, auth_dependency
from src.db.models import PendingToolApproval
from .models import PendingToolApprovalResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


@router.get("/", response_model=List[PendingToolApprovalResponse])
@limiter.limit("60/minute")
async def list_tool_approvals(
    db: db_dependency,
    auth: auth_dependency,
    request: Request,
    status: str = "pending",
):
    """
    Return tool approval requests for the authenticated account.

    Defaults to showing only pending requests; pass ?status=all to see all.
    Expired-but-still-pending records are automatically marked expired.
    """
    account_id = int(auth["id"]) if isinstance(auth["id"], str) else auth["id"]
    now = datetime.now(timezone.utc)

    query = db.query(PendingToolApproval).filter(
        PendingToolApproval.account_id == account_id
    )

    if status != "all":
        query = query.filter(PendingToolApproval.status == status)

    approvals = query.order_by(PendingToolApproval.created_at.desc()).all()

    # Lazily expire records that have passed their TTL
    for approval in approvals:
        if approval.status == "pending" and approval.expires_at < now:
            approval.status = "expired"

    if any(a.status == "expired" for a in approvals):
        db.commit()

    return approvals
