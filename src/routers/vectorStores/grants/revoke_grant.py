"""
Revoke a knowledge-base access grant (index owner or group manager).
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency, account_id_from_claims
from src.db.models import AccessGroup, VectorStoreAccessGrant
from src.services.access_group_roles import is_group_manager
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

router = APIRouter()


@router.delete("/grants/{grant_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def revoke_grant(
    grant_id: int,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request,
):
    """
    Revoke a knowledge-base grant.

    Allowed for the index owner OR a manager (owner/admin) of the granted group —
    either side of the grant can remove it.
    """
    try:
        account_id = account_id_from_claims(jwt)

        grant = db.query(VectorStoreAccessGrant).filter(VectorStoreAccessGrant.id == grant_id).first()
        if not grant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grant not found")

        if grant.owner_account_id != account_id:
            group = db.query(AccessGroup).filter(AccessGroup.id == grant.access_group_id).first()
            if not group or not is_group_manager(db, group, account_id):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to revoke this grant")

        db.delete(grant)
        db.commit()
        return None
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[REVOKE VS GRANT]")
