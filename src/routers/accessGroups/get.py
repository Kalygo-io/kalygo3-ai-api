"""
Get access group endpoint.
"""
from fastapi import APIRouter, HTTPException, status, Request
from sqlalchemy import func as sa_func
from src.deps import db_dependency, jwt_dependency
from src.db.models import AccessGroup, AccessGroupMember
from slowapi import Limiter
from slowapi.util import get_remote_address
from .models import AccessGroupResponse

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


@router.get("/{group_id}", response_model=AccessGroupResponse)
@limiter.limit("30/minute")
async def get_access_group(
    group_id: int,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request,
):
    """
    Get a specific access group.

    Accessible by the group owner or any member.
    """
    try:
        account_id = int(jwt['id']) if isinstance(jwt['id'], str) else jwt['id']

        group = db.query(AccessGroup).filter(AccessGroup.id == group_id).first()
        if not group:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Access group not found")

        # Owner or member?
        is_owner = group.owner_account_id == account_id
        is_member = False
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

        if not is_owner and not is_member:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Access group not found")

        member_count = (
            db.query(sa_func.count(AccessGroupMember.id))
            .filter(AccessGroupMember.access_group_id == group_id)
            .scalar()
        )

        return AccessGroupResponse(
            id=group.id,
            name=group.name,
            owner_account_id=group.owner_account_id,
            created_at=group.created_at,
            updated_at=group.updated_at,
            member_count=member_count,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get access group: {str(e)}",
        )
