"""
Grant an access group permission to use an agent (agent owner only).

Writes a unified AccessGrant (resource_type='agent', role='use').
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency, account_id_from_claims
from src.db.models import Agent, AccessGrant
from src.services import access
from src.services.access_admin import resolve_principal, upsert_grant
from .models import CreateGrantRequest, AgentAccessGrantResponse
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

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
    """Grant an access group permission to use this agent. Agent owner + group manager."""
    try:
        account_id = account_id_from_claims(jwt)

        agent = db.query(Agent).filter(
            Agent.id == agent_id,
            Agent.account_id == account_id,
        ).first()
        if not agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

        # Group-only sharing for agents (today's contract); enforces is_group_manager.
        principal_type, principal_id, label = resolve_principal(
            db,
            caller_account_id=account_id,
            access_group_id=body.accessGroupId,
            grantee_email=None,
        )

        existing = db.query(AccessGrant).filter(
            AccessGrant.principal_type == principal_type,
            AccessGrant.principal_id == principal_id,
            AccessGrant.resource_type == access.AGENT,
            AccessGrant.resource_id == agent_id,
        ).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Grant already exists for this group")

        grant = upsert_grant(
            db,
            principal_type=principal_type,
            principal_id=principal_id,
            resource_type=access.AGENT,
            resource_id=agent_id,
            role="use",
        )
        db.commit()
        db.refresh(grant)

        return AgentAccessGrantResponse(
            id=grant.id,
            agent_id=agent_id,
            access_group_id=principal_id,
            access_group_name=label,
            created_at=grant.created_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[CREATE GRANT]")
