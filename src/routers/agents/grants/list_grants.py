"""
List access grants for an agent (agent owner only). Reads unified AccessGrant.
"""
from fastapi import APIRouter, HTTPException, status, Request
from typing import List
from src.deps import db_dependency, jwt_dependency, account_id_from_claims
from src.db.models import Agent, AccessGroup, AccessGrant
from src.services import access
from .models import AgentAccessGrantResponse
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

router = APIRouter()

@router.get("/{agent_id}/access-grants", response_model=List[AgentAccessGrantResponse])
@limiter.limit("30/minute")
async def list_grants(
    agent_id: int,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request,
):
    """List access groups granted this agent. Agent owner only."""
    try:
        account_id = account_id_from_claims(jwt)

        agent = db.query(Agent).filter(
            Agent.id == agent_id,
            Agent.account_id == account_id,
        ).first()
        if not agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

        rows = (
            db.query(AccessGrant, AccessGroup.name)
            .join(AccessGroup, AccessGroup.id == AccessGrant.principal_id)
            .filter(
                AccessGrant.resource_type == access.AGENT,
                AccessGrant.resource_id == agent_id,
                AccessGrant.principal_type == access.GROUP,
            )
            .order_by(AccessGrant.created_at.desc())
            .all()
        )

        return [
            AgentAccessGrantResponse(
                id=grant.id,
                agent_id=agent_id,
                access_group_id=grant.principal_id,
                access_group_name=group_name,
                created_at=grant.created_at,
            )
            for grant, group_name in rows
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise handle_db_error(e, "[LIST GRANTS]")
