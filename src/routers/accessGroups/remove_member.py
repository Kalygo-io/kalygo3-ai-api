"""
Remove member from access group endpoint (owner only).
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency, account_id_from_claims
from src.db.models import AccessGroup, AccessGroupMember
from src.services.access_group_roles import is_group_manager, is_group_owner, ADMIN_ROLE
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

router = APIRouter()

@router.delete("/{group_id}/members/{member_account_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def remove_member(
    group_id: int,
    member_account_id: int,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request,
):
    """Remove a member from the access group. Owner only."""
    try:
        account_id = account_id_from_claims(jwt)

        group = db.query(AccessGroup).filter(AccessGroup.id == group_id).first()
        if not group:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Access group not found")
        if not is_group_manager(db, group, account_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to manage this group")

        member = db.query(AccessGroupMember).filter(
            AccessGroupMember.access_group_id == group_id,
            AccessGroupMember.account_id == member_account_id,
        ).first()
        if not member:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found in this group")

        # Removing an admin is owner-only (admins can only remove regular members).
        if member.role == ADMIN_ROLE and not is_group_owner(group, account_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the group owner can remove an admin")

        db.delete(member)
        db.commit()
        return None
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[REMOVE MEMBER]")
