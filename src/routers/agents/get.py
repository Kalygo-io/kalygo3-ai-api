"""
Get agent details endpoint.
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency
from src.db.models import Agent, Account
from slowapi import Limiter
from slowapi.util import get_remote_address
from .models import AgentResponse

limiter = Limiter(key_func=get_remote_address)

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
    Only returns agents belonging to the authenticated user.
    """
    try:
        account_id = int(jwt['id']) if isinstance(jwt['id'], str) else jwt['id']
        account = db.query(Account).filter(Account.id == account_id).first()
        
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Account not found"
            )
        
        # Query agent by ID and account_id to ensure it belongs to the user
        agent = db.query(Agent).filter(
            Agent.id == agent_id,
            Agent.account_id == account_id
        ).first()
        
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent not found"
            )
        
        return AgentResponse(
            id=agent.id,
            name=agent.name,
            config=agent.config
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid agent ID: {str(e)}"
        )
    except Exception as e:
        print(f"Error retrieving agent: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while retrieving agent: {str(e)}"
        )
