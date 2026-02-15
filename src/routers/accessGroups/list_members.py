"""
List members of an access group endpoint (owner or member).
"""
from fastapi import APIRouter, HTTPException, status, Request
from typing import List
from src.deps import db_dependency, jwt_dependency
from src.db.models import AccessGroup, AccessGroupMember, Account
from slowapi import Limiter
from slowapi.util import get_remote_address
from .models import AccessGroupMemberResponse

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


@router.get("/{group_id}/members", response_model=List[AccessGroupMemberResponse])
@limiter.limit("30/minute")
async def list_members(
    group_id: int,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request,
):
    """
    List all members of an access group.

    Accessible by the group owner or any member of the group.
    """
    try:
        account_id = int(jwt['id']) if isinstance(jwt['id'], str) else jwt['id']

        group = db.query(AccessGroup).filter(AccessGroup.id == group_id).first()
        if not group:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Access group not found")

        # Owner or member?
        is_owner = group.owner_account_id == account_id
        if not is_owner:
            is_member = (
                db.query(AccessGroupMember)
                .filter(
                    AccessGroupMember.access_group_id == group_id,
                    AccessGroupMember.account_id == account_id,
                )
                .first()
                is not None
            )
            if not is_member:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Access group not found")

        # Fetch members with account emails
        rows = (
            db.query(AccessGroupMember, Account.email)
            .join(Account, Account.id == AccessGroupMember.account_id)
            .filter(AccessGroupMember.access_group_id == group_id)
            .order_by(AccessGroupMember.created_at.asc())
            .all()
        )

        return [
            AccessGroupMemberResponse(
                id=member.id,
                account_id=member.account_id,
                email=email,
                created_at=member.created_at,
            )
            for member, email in rows
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list members: {str(e)}",
        )
