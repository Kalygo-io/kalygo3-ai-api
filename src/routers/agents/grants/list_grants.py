"""
List access grants for an agent (agent owner only). Reads unified AccessGrant.
"""
from fastapi import APIRouter, HTTPException, status, Request
from typing import List
from src.deps import db_dependency, jwt_dependency, account_id_from_claims
from src.db.models import Agent, AccessGrant
from src.services import access
from src.services.access_admin import grant_label
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
    """List who an agent is shared with (groups + individuals). Agent owner only."""
    try:
        account_id = account_id_from_claims(jwt)

        agent = db.query(Agent).filter(
            Agent.id == agent_id,
            Agent.account_id == account_id,
        ).first()
        if not agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

        grants = (
            db.query(AccessGrant)
            .filter(
                AccessGrant.resource_type == access.AGENT,
                AccessGrant.resource_id == agent_id,
            )
            .order_by(AccessGrant.created_at.desc())
            .all()
        )

        return [
            AgentAccessGrantResponse(
                id=g.id,
                agent_id=agent_id,
                access_group_id=g.principal_id if g.principal_type == access.GROUP else None,
                grantee_account_id=g.principal_id if g.principal_type == access.ACCOUNT else None,
                label=grant_label(db, g),
                target_type="group" if g.principal_type == access.GROUP else "individual",
                created_at=g.created_at,
            )
            for g in grants
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise handle_db_error(e, "[LIST GRANTS]")
