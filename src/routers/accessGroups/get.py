"""
Get access group endpoint.
"""
from fastapi import APIRouter, HTTPException, status, Request
from sqlalchemy import func as sa_func
from src.deps import db_dependency, jwt_dependency, account_id_from_claims
from src.db.models import AccessGroup, AccessGroupMember
from .models import AccessGroupResponse
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

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
        account_id = account_id_from_claims(jwt)

        group = db.query(AccessGroup).filter(AccessGroup.id == group_id).first()
        if not group:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Access group not found")

        # Owner or member?
        is_owner = group.owner_account_id == account_id
        member_row = None
        if not is_owner:
            member_row = (
                db.query(AccessGroupMember)
                .filter(
                    AccessGroupMember.access_group_id == group_id,
                    AccessGroupMember.account_id == account_id,
                )
                .first()
            )

        if not is_owner and member_row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Access group not found")

        my_role = "owner" if is_owner else member_row.role

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
            my_role=my_role,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise handle_db_error(e, "[GET ACCESS GROUP]")
