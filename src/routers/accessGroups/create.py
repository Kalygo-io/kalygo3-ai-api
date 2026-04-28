"""
Create access group endpoint.
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency
from src.db.models import AccessGroup
from .models import CreateAccessGroupRequest, AccessGroupResponse
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

router = APIRouter()

@router.post("/", response_model=AccessGroupResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def create_access_group(
    body: CreateAccessGroupRequest,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request,
):
    """Create a new access group. The authenticated user becomes the owner."""
    try:
        account_id = int(jwt['id']) if isinstance(jwt['id'], str) else jwt['id']

        group = AccessGroup(
            name=body.name,
            owner_account_id=account_id,
        )
        db.add(group)
        db.commit()
        db.refresh(group)

        return AccessGroupResponse(
            id=group.id,
            name=group.name,
            owner_account_id=group.owner_account_id,
            created_at=group.created_at,
            updated_at=group.updated_at,
            member_count=0,
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[CREATE ACCESS GROUP]")
