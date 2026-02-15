"""
Update access group endpoint (owner only).
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency
from src.db.models import AccessGroup
from slowapi import Limiter
from slowapi.util import get_remote_address
from .models import UpdateAccessGroupRequest, AccessGroupResponse

limiter = Limiter(key_func=get_remote_address)
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
        account_id = int(jwt['id']) if isinstance(jwt['id'], str) else jwt['id']

        group = db.query(AccessGroup).filter(
            AccessGroup.id == group_id,
            AccessGroup.owner_account_id == account_id,
        ).first()

        if not group:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Access group not found")

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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update access group: {str(e)}",
        )
