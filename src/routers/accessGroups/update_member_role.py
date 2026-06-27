"""
Promote/demote a group member's role (owner only).
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency, account_id_from_claims
from src.db.models import AccessGroup, AccessGroupMember, Account
from .models import UpdateMemberRoleRequest, AccessGroupMemberResponse
from src.services.access_group_roles import is_group_owner
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

router = APIRouter()

@router.patch("/{group_id}/members/{member_account_id}/role", response_model=AccessGroupMemberResponse)
@limiter.limit("10/minute")
async def update_member_role(
    group_id: int,
    member_account_id: int,
    body: UpdateMemberRoleRequest,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request,
):
    """Set a member's role to 'admin' or 'member'. Owner only."""
    try:
        account_id = account_id_from_claims(jwt)

        group = db.query(AccessGroup).filter(AccessGroup.id == group_id).first()
        if not group:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Access group not found")
        if not is_group_owner(group, account_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the group owner can change member roles")

        member = db.query(AccessGroupMember).filter(
            AccessGroupMember.access_group_id == group_id,
            AccessGroupMember.account_id == member_account_id,
        ).first()
        if not member:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found in this group")

        member.role = body.role
        db.commit()
        db.refresh(member)

        account = db.query(Account).filter(Account.id == member.account_id).first()

        return AccessGroupMemberResponse(
            id=member.id,
            account_id=member.account_id,
            email=account.email if account else "",
            role=member.role,
            created_at=member.created_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[UPDATE MEMBER ROLE]")
