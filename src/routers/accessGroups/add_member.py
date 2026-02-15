"""
Add member to access group endpoint (owner only).
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency
from src.db.models import AccessGroup, AccessGroupMember, Account
from slowapi import Limiter
from slowapi.util import get_remote_address
from .models import AddMemberRequest, AccessGroupMemberResponse

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


@router.post("/{group_id}/members", response_model=AccessGroupMemberResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def add_member(
    group_id: int,
    body: AddMemberRequest,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request,
):
    """
    Add an account to the access group by email. Owner only.

    Validates that:
    - The group exists and caller is the owner.
    - The target account exists.
    - The target is not already a member.
    """
    try:
        account_id = int(jwt['id']) if isinstance(jwt['id'], str) else jwt['id']

        group = db.query(AccessGroup).filter(
            AccessGroup.id == group_id,
            AccessGroup.owner_account_id == account_id,
        ).first()
        if not group:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Access group not found")

        # Resolve target account by email
        target_account = db.query(Account).filter(Account.email == body.email).first()
        if not target_account:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found for the given email")

        # Check for duplicate
        existing = db.query(AccessGroupMember).filter(
            AccessGroupMember.access_group_id == group_id,
            AccessGroupMember.account_id == target_account.id,
        ).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Account is already a member of this group")

        member = AccessGroupMember(
            access_group_id=group_id,
            account_id=target_account.id,
        )
        db.add(member)
        db.commit()
        db.refresh(member)

        return AccessGroupMemberResponse(
            id=member.id,
            account_id=target_account.id,
            email=target_account.email,
            created_at=member.created_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add member: {str(e)}",
        )
