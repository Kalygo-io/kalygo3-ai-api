"""
Revoke an access group's permission to use an agent.

Allowed for the agent owner OR a manager of the granted group. Operates on the
unified AccessGrant table (resource_type='agent').
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency, account_id_from_claims
from src.db.models import Agent, AccessGroup, AccessGrant
from src.services import access
from src.services.access_group_roles import is_group_manager
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

router = APIRouter()

@router.delete("/{agent_id}/access-grants/{access_group_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def revoke_grant(
    agent_id: int,
    access_group_id: int,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request,
):
    """Revoke a group's access to this agent. Agent owner or group manager."""
    try:
        account_id = account_id_from_claims(jwt)

        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

        if agent.account_id != account_id:
            group = db.query(AccessGroup).filter(AccessGroup.id == access_group_id).first()
            if not group or not is_group_manager(db, group, account_id):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to revoke this grant")

        grant = db.query(AccessGrant).filter(
            AccessGrant.principal_type == access.GROUP,
            AccessGrant.principal_id == access_group_id,
            AccessGrant.resource_type == access.AGENT,
            AccessGrant.resource_id == agent_id,
        ).first()
        if not grant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grant not found")

        db.delete(grant)
        db.commit()
        return None
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[REVOKE GRANT]")
