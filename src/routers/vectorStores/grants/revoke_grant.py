"""
Revoke a knowledge-base access grant (index owner or group manager).
Operates on the unified AccessGrant table (resource_type='vector_store').
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency, account_id_from_claims
from src.db.models import AccessGroup, AccessGrant, VectorStore
from src.services import access
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
    """Revoke a KB grant. Allowed for the index owner OR a manager of the granted group."""
    try:
        account_id = account_id_from_claims(jwt)

        grant = db.query(AccessGrant).filter(
            AccessGrant.id == grant_id,
            AccessGrant.resource_type == access.VECTOR_STORE,
        ).first()
        if not grant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grant not found")

        store = db.query(VectorStore).filter(VectorStore.id == grant.resource_id).first()
        is_owner = store is not None and store.owner_account_id == account_id

        if not is_owner:
            # A manager of the granted group may also remove a group grant.
            allowed = False
            if grant.principal_type == access.GROUP:
                group = db.query(AccessGroup).filter(AccessGroup.id == grant.principal_id).first()
                allowed = bool(group and is_group_manager(db, group, account_id))
            if not allowed:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to revoke this grant")

        db.delete(grant)
        db.commit()
        return None
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[REVOKE VS GRANT]")
