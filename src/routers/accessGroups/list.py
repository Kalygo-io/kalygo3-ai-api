"""
List access groups endpoint.

Returns groups the user owns as well as groups they are a member of.
"""
from fastapi import APIRouter, HTTPException, status, Request
from typing import List
from sqlalchemy import or_, func as sa_func
from src.deps import db_dependency, jwt_dependency, account_id_from_claims
from src.db.models import AccessGroup, AccessGroupMember
from .models import AccessGroupResponse
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

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
        account_id = account_id_from_claims(jwt)

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

        # The caller's role in each group they belong to (for my_role gating).
        my_member_roles = dict(
            db.query(AccessGroupMember.access_group_id, AccessGroupMember.role)
            .filter(AccessGroupMember.account_id == account_id)
            .all()
        )

        return [
            AccessGroupResponse(
                id=g.id,
                name=g.name,
                owner_account_id=g.owner_account_id,
                created_at=g.created_at,
                updated_at=g.updated_at,
                member_count=counts.get(g.id, 0),
                my_role=(
                    "owner"
                    if g.owner_account_id == account_id
                    else my_member_roles.get(g.id, "member")
                ),
            )
            for g in groups
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise handle_db_error(e, "[LIST ACCESS GROUPS]")
