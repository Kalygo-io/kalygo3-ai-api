"""
List access grants for an agent (agent owner only).
"""
from fastapi import APIRouter, HTTPException, status, Request
from typing import List
from src.deps import db_dependency, jwt_dependency
from src.db.models import Agent, AccessGroup, AgentAccessGrant
from slowapi import Limiter
from slowapi.util import get_remote_address
from .models import AgentAccessGrantResponse

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


@router.get("/{agent_id}/access-grants", response_model=List[AgentAccessGrantResponse])
@limiter.limit("30/minute")
async def list_grants(
    agent_id: int,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request,
):
    """List all access groups that have been granted access to this agent. Agent owner only."""
    try:
        account_id = int(jwt['id']) if isinstance(jwt['id'], str) else jwt['id']

        # Verify agent ownership
        agent = db.query(Agent).filter(
            Agent.id == agent_id,
            Agent.account_id == account_id,
        ).first()
        if not agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

        rows = (
            db.query(AgentAccessGrant, AccessGroup.name)
            .join(AccessGroup, AccessGroup.id == AgentAccessGrant.access_group_id)
            .filter(AgentAccessGrant.agent_id == agent_id)
            .order_by(AgentAccessGrant.created_at.desc())
            .all()
        )

        return [
            AgentAccessGrantResponse(
                id=grant.id,
                agent_id=grant.agent_id,
                access_group_id=grant.access_group_id,
                access_group_name=group_name,
                created_at=grant.created_at,
            )
            for grant, group_name in rows
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list grants: {str(e)}",
        )
