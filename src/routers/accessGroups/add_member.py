"""
Add member to access group endpoint (owner only).
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency, account_id_from_claims
from src.db.models import AccessGroup, AccessGroupMember, Account
from .models import AddMemberRequest, AccessGroupMemberResponse
from src.services.access_group_roles import is_group_manager, MEMBER_ROLE
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

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
        account_id = account_id_from_claims(jwt)

        group = db.query(AccessGroup).filter(AccessGroup.id == group_id).first()
        if not group:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Access group not found")
        if not is_group_manager(db, group, account_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to manage this group")

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
            role=MEMBER_ROLE,
        )
        db.add(member)
        db.commit()
        db.refresh(member)

        return AccessGroupMemberResponse(
            id=member.id,
            account_id=target_account.id,
            email=target_account.email,
            role=member.role,
            created_at=member.created_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[ADD MEMBER]")
