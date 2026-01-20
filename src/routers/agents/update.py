"""
Update agent endpoint.
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency
from src.db.models import Agent, Account
from src.schemas import validate_against_schema
from jsonschema import ValidationError as JsonSchemaValidationError
from slowapi import Limiter
from slowapi.util import get_remote_address
from .models import UpdateAgentRequest, AgentResponse

limiter = Limiter(key_func=get_remote_address)

router = APIRouter()


@router.put("/{agent_id}", response_model=AgentResponse)
@limiter.limit("10/minute")
async def update_agent(
    agent_id: int,
    request_body: UpdateAgentRequest,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request
):
    """
    Update an agent by ID.
    
    Allows updating:
    - name: The name of the agent (optional)
    - config: Agent configuration object (optional)
    
    The config must follow the agent_config schema structure if provided.
    
    Supported versions:
    
    Version 1 (Knowledge Base-centric):
    {
      "schema": "agent_config",
      "version": 1,
      "data": {
        "systemPrompt": "The system prompt for the agent",
        "knowledgeBases": [...]
      }
    }
    
    Version 2 (Tool-centric, recommended):
    {
      "schema": "agent_config",
      "version": 2,
      "data": {
        "systemPrompt": "The system prompt for the agent",
        "tools": [
          {
            "type": "vectorSearch",
            "provider": "pinecone",
            "index": "index-name",
            "namespace": "namespace",
            "topK": 10
          }
        ]
      }
    }
    
    Only allows updating agents belonging to the authenticated user.
    The account_id (owner) cannot be changed.
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
        
        # Check if at least one field is being updated
        if request_body.name is None and request_body.config is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one field (name or config) must be provided for update"
            )
        
        # Update name if provided
        if request_body.name is not None:
            agent_name = request_body.name.strip()
            if not agent_name:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Agent name cannot be empty"
                )
            agent.name = agent_name
        
        # Update config if provided
        if request_body.config is not None:
            # Extract version from config to validate against the correct schema
            config_version = request_body.config.get("version", 1)
            
            # Validate version is supported
            if config_version not in [1, 2]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unsupported config version: {config_version}. Supported versions: 1, 2"
                )
            
            print(f"[UPDATE AGENT] Validating against agent_config v{config_version}")
            
            # Validate config structure against agent_config schema
            try:
                validate_against_schema(request_body.config, "agent_config", config_version)
            except JsonSchemaValidationError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Config validation failed for schema 'agent_config' v{config_version}: {str(e)}"
                )
            except FileNotFoundError as e:
                print(f"Warning: Config schema validation skipped - {str(e)}")
            
            agent.config = request_body.config
        
        # Validate the updated agent structure if both fields are present
        if request_body.name is not None and request_body.config is not None:
            # Use the version from the updated config
            config_version = agent.config.get("version", 1)
            
            # Create a full agent structure for validation
            agent_dict = {
                "name": agent.name,
                "config": agent.config
            }
            try:
                validate_against_schema(agent_dict, "agent", config_version)
            except JsonSchemaValidationError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Validation failed for schema 'agent' v{config_version}: {str(e)}"
                )
            except FileNotFoundError as e:
                print(f"Warning: Agent schema validation skipped - {str(e)}")
        
        # Commit the changes
        db.commit()
        db.refresh(agent)
        
        return AgentResponse(
            id=agent.id,
            name=agent.name,
            config=agent.config
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid agent ID: {str(e)}"
        )
    except Exception as e:
        db.rollback()
        print(f"Error updating agent: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while updating agent: {str(e)}"
        )
