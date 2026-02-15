"""
List access groups endpoint.

Returns groups the user owns as well as groups they are a member of.
"""
from fastapi import APIRouter, HTTPException, status, Request
from typing import List
from sqlalchemy import or_, func as sa_func
from src.deps import db_dependency, jwt_dependency
from src.db.models import AccessGroup, AccessGroupMember
from slowapi import Limiter
from slowapi.util import get_remote_address
from .models import AccessGroupResponse

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


@router.get("/", response_model=List[AccessGroupResponse])
@limiter.limit("30/minute")
async def list_access_groups(
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request,
):
    """
    List access groups the authenticated user owns **or** is a member of.
    """
    try:
        account_id = int(jwt['id']) if isinstance(jwt['id'], str) else jwt['id']

        # IDs of groups the user is a member of
        member_group_ids_q = (
            db.query(AccessGroupMember.access_group_id)
            .filter(AccessGroupMember.account_id == account_id)
            .subquery()
        )

        groups = (
            db.query(AccessGroup)
            .filter(
                or_(
                    AccessGroup.owner_account_id == account_id,
                    AccessGroup.id.in_(db.query(member_group_ids_q)),
                )
            )
            .order_by(AccessGroup.id.desc())
            .all()
        )

        # Pre-fetch member counts in one query
        counts = dict(
            db.query(AccessGroupMember.access_group_id, sa_func.count(AccessGroupMember.id))
            .filter(AccessGroupMember.access_group_id.in_([g.id for g in groups]))
            .group_by(AccessGroupMember.access_group_id)
            .all()
        ) if groups else {}

        return [
            AccessGroupResponse(
                id=g.id,
                name=g.name,
                owner_account_id=g.owner_account_id,
                created_at=g.created_at,
                updated_at=g.updated_at,
                member_count=counts.get(g.id, 0),
            )
            for g in groups
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list access groups: {str(e)}",
        )
