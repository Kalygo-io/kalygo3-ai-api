"""
Update access group endpoint (owner only).
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency, account_id_from_claims
from src.db.models import AccessGroup
from .models import UpdateAccessGroupRequest, AccessGroupResponse
from src.services.access_group_roles import is_group_manager
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

router = APIRouter()

@router.patch("/{group_id}", response_model=AccessGroupResponse)
@limiter.limit("10/minute")
async def update_access_group(
    group_id: int,
    body: UpdateAccessGroupRequest,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request,
):
    """Update an access group's name. Owner only."""
    try:
        account_id = account_id_from_claims(jwt)

        group = db.query(AccessGroup).filter(AccessGroup.id == group_id).first()
        if not group:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Access group not found")
        if not is_group_manager(db, group, account_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to manage this group")

        group.name = body.name
        db.commit()
        db.refresh(group)

        return AccessGroupResponse(
            id=group.id,
            name=group.name,
            owner_account_id=group.owner_account_id,
            created_at=group.created_at,
            updated_at=group.updated_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[UPDATE ACCESS GROUP]")
