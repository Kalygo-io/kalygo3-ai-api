"""
Revoke an access group's permission to use an agent (agent owner only).
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency, account_id_from_claims
from src.db.models import Agent, AccessGroup, AgentAccessGrant
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
    """
    Revoke an access group's permission to use this agent.

    Allowed for the agent owner OR a manager (owner/admin) of the group — either
    side of the grant can remove it.
    """
    try:
        account_id = account_id_from_claims(jwt)

        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

        # Authorization: agent owner, or owner/admin of the group the agent is granted to.
        if agent.account_id != account_id:
            group = db.query(AccessGroup).filter(AccessGroup.id == access_group_id).first()
            if not group or not is_group_manager(db, group, account_id):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to revoke this grant")

        grant = db.query(AgentAccessGrant).filter(
            AgentAccessGrant.agent_id == agent_id,
            AgentAccessGrant.access_group_id == access_group_id,
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
