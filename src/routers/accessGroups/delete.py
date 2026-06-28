"""
Delete access group endpoint (owner only).

Cascading FKs will remove members and agent grants automatically.
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency, account_id_from_claims
from src.db.models import AccessGroup, AccessGroupMember
from src.services.credential_access import prune_unusable_defaults_for_account
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

router = APIRouter()

@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def delete_access_group(
    group_id: int,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request,
):
    """Delete an access group. Owner only. Cascades members and grants."""
    try:
        account_id = account_id_from_claims(jwt)

        group = db.query(AccessGroup).filter(
            AccessGroup.id == group_id,
            AccessGroup.owner_account_id == account_id,
        ).first()

        if not group:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Access group not found")

        # Capture members before the cascade removes them: deleting the group also
        # cascades its credential grants, which may strip a member's only access to
        # a shared credential they had marked default.
        member_ids = [
            r[0]
            for r in db.query(AccessGroupMember.account_id)
            .filter(AccessGroupMember.access_group_id == group_id)
            .all()
        ]

        db.delete(group)
        db.flush()  # apply the cascade so credential access re-checks reflect it

        for member_id in member_ids:
            prune_unusable_defaults_for_account(db, member_id)

        db.commit()
        return None
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[DELETE ACCESS GROUP]")
