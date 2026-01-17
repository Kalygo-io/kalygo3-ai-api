"""
List agents endpoint.
"""
from fastapi import APIRouter, HTTPException, status, Request
from typing import List
from src.deps import db_dependency, jwt_dependency
from src.db.models import Agent, Account
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
    List all agents belonging to the authenticated user.
    
    Returns a list of all agents associated with the current user's account.
    """
    try:
        account_id = int(jwt['id']) if isinstance(jwt['id'], str) else jwt['id']
        account = db.query(Account).filter(Account.id == account_id).first()
        
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Account not found"
            )
        
        # Query all agents for this account
        agents = db.query(Agent).filter(
            Agent.account_id == account_id
        ).order_by(Agent.id.desc()).all()
        
        return [
            AgentResponse(
                id=agent.id,
                name=agent.name,
                config=agent.config
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
