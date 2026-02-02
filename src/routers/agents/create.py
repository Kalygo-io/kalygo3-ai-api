"""
Create agent endpoint.
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency
from src.db.models import Agent, Account
from src.schemas import validate_against_schema
from jsonschema import ValidationError as JsonSchemaValidationError
from slowapi import Limiter
from slowapi.util import get_remote_address
from .models import CreateAgentRequest, AgentResponse

limiter = Limiter(key_func=get_remote_address)

router = APIRouter()


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=AgentResponse)
@limiter.limit("10/minute")
async def create_agent(
    request_body: CreateAgentRequest,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request
):
    """
    Create a new agent.
    
    The agent will have:
    - name: The name of the agent (required)
    - config: Agent configuration object (required)
    
    The config must include schema, version, and data.
    
    Supported versions:
    
    Version 1 (Knowledge Base-centric):
    {
      "schema": "agent_config",
      "version": 1,
      "data": {
        "systemPrompt": "The system prompt for the agent",
        "knowledgeBases": [
          {
            "provider": "pinecone",
            "index": "all-MiniLM-L6-v2",
            "namespace": "ai_school_kb",
            "description": "Optional description"
          }
        ]
      }
    }
    
    Version 2 (Tool-centric):
    {
      "schema": "agent_config",
      "version": 2,
      "data": {
        "systemPrompt": "The system prompt for the agent",
        "tools": [
          {
            "type": "vectorSearch",
            "provider": "pinecone",
            "index": "all-MiniLM-L6-v2",
            "namespace": "ai_school_kb",
            "description": "Optional description",
            "topK": 10
          }
        ]
      }
    }
    
    Version 3 (Model configuration, recommended):
    {
      "schema": "agent_config",
      "version": 3,
      "data": {
        "systemPrompt": "The system prompt for the agent",
        "model": {
          "provider": "openai",
          "model": "gpt-4o-mini"
        },
        "tools": []
      }
    }
    
    Supported model providers: openai, anthropic, ollama
    
    The request body is validated against the agent JSON schema matching the version
    specified in the config (v1, v2, or v3).
    """
    try:
        account_id = int(jwt['id']) if isinstance(jwt['id'], str) else jwt['id']
        account = db.query(Account).filter(Account.id == account_id).first()
        
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Account not found"
            )
        
        # Validate agent name
        agent_name = request_body.name.strip()
        if not agent_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Agent name cannot be empty"
            )
        
        # Extract version from config to validate against the correct schema
        config_version = request_body.config.get("version", 1)
        
        # Validate version is supported
        if config_version not in [1, 2, 3]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported config version: {config_version}. Supported versions: 1, 2, 3"
            )
        
        print(f"[CREATE AGENT] Validating against agent_config v{config_version}")
        
        # Convert Pydantic model to dict for JSON schema validation
        request_dict = request_body.model_dump(exclude_none=False)
        
        # Validate against JSON schema (validates name and full config structure including schema/version/data)
        try:
            validate_against_schema(request_dict, "agent", config_version)
        except JsonSchemaValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Validation failed for schema 'agent' v{config_version}: {str(e)}"
            )
        except FileNotFoundError as e:
            # Schema file not found - log error but don't fail the request
            print(f"Warning: Schema validation skipped - {str(e)}")
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Schema validation error: {str(e)}"
            )
        
        # Validate config structure separately against agent_config schema (validates schema, version, and data)
        try:
            validate_against_schema(request_body.config, "agent_config", config_version)
        except JsonSchemaValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Config validation failed for schema 'agent_config' v{config_version}: {str(e)}"
            )
        except FileNotFoundError as e:
            print(f"Warning: Config schema validation skipped - {str(e)}")
        
        # Create the agent with the provided config (already includes schema, version, and data)
        agent = Agent(
            account_id=account_id,
            name=agent_name,
            config=request_body.config
        )
        
        db.add(agent)
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
            detail=str(e)
        )
    except Exception as e:
        db.rollback()
        print(f"Error creating agent: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while creating agent: {str(e)}"
        )
