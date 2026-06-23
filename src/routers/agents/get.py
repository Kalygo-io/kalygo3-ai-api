"""
Get agent details endpoint.

Uses ``can_access_agent`` so that both owners and group members can
retrieve agent details.  Returns 404 when access is denied to avoid
leaking existence.
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency, account_id_from_claims, ensure_account
from src.db.models import Agent
from src.services.agent_access import can_access_agent
from .models import AgentResponse
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

router = APIRouter()

@router.get("/{agent_id}", response_model=AgentResponse)
@limiter.limit("30/minute")
async def get_agent(
    agent_id: int,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request
):
    """
    Get a specific agent by ID.

    Returns agents the authenticated user owns **or** has access to via
    an access group.  Returns 404 when the agent does not exist or the
    user has no access (to avoid leaking existence).
    """
    try:
        account_id = account_id_from_claims(jwt)
        account = ensure_account(db, account_id)
        
        # Load agent by ID (no ownership filter – access check follows)
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        
        if not agent or not can_access_agent(db, account_id, agent_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent not found"
            )
        
        return AgentResponse(
            id=agent.id,
            name=agent.name,
            config=agent.config,
            is_owner=(agent.account_id == account_id),
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        raise handle_db_error(e, "[GET AGENT VALUE ERROR]")
    except Exception as e:
        raise handle_db_error(e, "[ERROR RETRIEVING AGENT]")
