"""
List agents endpoint.

Returns agents the authenticated user owns as well as agents shared
with them via access groups.
"""
from fastapi import APIRouter, HTTPException, status, Request
from typing import List
from sqlalchemy import or_
from src.deps import db_dependency, jwt_dependency
from src.db.models import Agent, Account
from src.services.agent_access import get_accessible_agent_ids
from slowapi import Limiter
from slowapi.util import get_remote_address
from .models import AgentResponse

limiter = Limiter(key_func=get_remote_address)

router = APIRouter()


@router.get("/", response_model=List[AgentResponse])
@limiter.limit("30/minute")
async def list_agents(
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request
):
    """
    List all agents the authenticated user can access.

    This includes agents the user owns as well as agents shared with
    them via access groups.  Each response item includes ``is_owner``
    so the UI can distinguish owned vs. shared agents.
    """
    try:
        account_id = int(jwt['id']) if isinstance(jwt['id'], str) else jwt['id']
        account = db.query(Account).filter(Account.id == account_id).first()
        
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Account not found"
            )
        
        # IDs the user can access via group grants (excludes owned)
        granted_ids = get_accessible_agent_ids(db, account_id)

        # Single query: owned OR granted
        if granted_ids:
            agents = (
                db.query(Agent)
                .filter(
                    or_(
                        Agent.account_id == account_id,
                        Agent.id.in_(granted_ids),
                    )
                )
                .order_by(Agent.id.desc())
                .all()
            )
        else:
            agents = (
                db.query(Agent)
                .filter(Agent.account_id == account_id)
                .order_by(Agent.id.desc())
                .all()
            )
        
        return [
            AgentResponse(
                id=agent.id,
                name=agent.name,
                config=agent.config,
                is_owner=(agent.account_id == account_id),
            )
            for agent in agents
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error listing agents: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while listing agents: {str(e)}"
        )
