"""
Revoke an agent access grant by grant id (agent owner or, for group grants, a
manager of the granted group). Operates on the unified AccessGrant table.
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency, account_id_from_claims
from src.db.models import Agent, AccessGroup, AccessGrant
from src.services import access
from src.services.access_admin import record_access_event
from src.services.access_group_roles import is_group_manager
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

router = APIRouter()

@router.delete("/{agent_id}/access-grants/{grant_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def revoke_grant(
    agent_id: int,
    grant_id: int,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request,
):
    """Revoke a grant on this agent. Agent owner, or a manager of the granted group."""
    try:
        account_id = account_id_from_claims(jwt)

        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

        grant = db.query(AccessGrant).filter(
            AccessGrant.id == grant_id,
            AccessGrant.resource_type == access.AGENT,
            AccessGrant.resource_id == agent_id,
        ).first()
        if not grant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grant not found")

        if agent.account_id != account_id:
            # Non-owner may only revoke a group grant they manage.
            allowed = False
            if grant.principal_type == access.GROUP:
                group = db.query(AccessGroup).filter(AccessGroup.id == grant.principal_id).first()
                allowed = bool(group and is_group_manager(db, group, account_id))
            if not allowed:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to revoke this grant")

        record_access_event(
            db,
            event_type="revoke",
            actor_account_id=account_id,
            resource_type=access.AGENT,
            resource_id=agent_id,
            principal_type=grant.principal_type,
            principal_id=grant.principal_id,
            role=grant.role,
        )
        db.delete(grant)
        db.commit()
        return None
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[REVOKE GRANT]")
