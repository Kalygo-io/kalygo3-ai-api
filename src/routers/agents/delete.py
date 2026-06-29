"""
Delete agent endpoint.
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency, account_id_from_claims, ensure_account
from src.db.models import Agent
from src.services import access
from src.services.access_admin import revoke_resource_grants_logged
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

router = APIRouter()

@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def delete_agent(
    agent_id: int,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request
):
    """
    Delete an agent by ID.
    Only allows deleting agents belonging to the authenticated user.
    """
    try:
        account_id = account_id_from_claims(jwt)
        account = ensure_account(db, account_id)
        
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
        
        # Remove sharing grants on this agent (polymorphic grants have no FK
        # cascade), logging a revoke event for each before the agent is gone.
        revoke_resource_grants_logged(
            db, resource_type=access.AGENT, resource_id=agent_id, actor_account_id=account_id
        )

        # Delete the agent
        db.delete(agent)
        db.commit()

        return None
        
    except HTTPException:
        raise
    except ValueError as e:
        db.rollback()
        raise handle_db_error(e, "[DELETE AGENT VALUE ERROR]")
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[ERROR DELETING AGENT]")
