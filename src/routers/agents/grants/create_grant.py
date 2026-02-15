"""
Grant an access group permission to use an agent (agent owner only).
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency
from src.db.models import Agent, AccessGroup, AgentAccessGrant
from slowapi import Limiter
from slowapi.util import get_remote_address
from .models import CreateGrantRequest, AgentAccessGrantResponse

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


@router.post("/{agent_id}/access-grants", response_model=AgentAccessGrantResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def create_grant(
    agent_id: int,
    body: CreateGrantRequest,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request,
):
    """
    Grant an access group permission to use this agent.

    Only the agent owner can create grants.  For v1 the caller must also
    own the access group.
    """
    try:
        account_id = int(jwt['id']) if isinstance(jwt['id'], str) else jwt['id']

        # Verify agent ownership
        agent = db.query(Agent).filter(
            Agent.id == agent_id,
            Agent.account_id == account_id,
        ).first()
        if not agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

        # Verify access group exists and caller owns it (v1 restriction)
        group = db.query(AccessGroup).filter(
            AccessGroup.id == body.accessGroupId,
            AccessGroup.owner_account_id == account_id,
        ).first()
        if not group:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Access group not found")

        # Check for duplicate grant
        existing = db.query(AgentAccessGrant).filter(
            AgentAccessGrant.agent_id == agent_id,
            AgentAccessGrant.access_group_id == body.accessGroupId,
        ).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Grant already exists for this group")

        grant = AgentAccessGrant(
            agent_id=agent_id,
            access_group_id=body.accessGroupId,
        )
        db.add(grant)
        db.commit()
        db.refresh(grant)

        return AgentAccessGrantResponse(
            id=grant.id,
            agent_id=grant.agent_id,
            access_group_id=grant.access_group_id,
            access_group_name=group.name,
            created_at=grant.created_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create grant: {str(e)}",
        )
