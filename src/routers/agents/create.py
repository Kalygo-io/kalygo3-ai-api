"""
Create agent endpoint.
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency
from src.db.models import Agent, Account
from src.schemas import validate_against_schema
from jsonschema import ValidationError as JsonSchemaValidationError
from .models import CreateAgentRequest, AgentResponse
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

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
    Create a new agent with a v4 config:
    {
      "schema": "agent_config",
      "version": 4,
      "data": {
        "systemPrompt": "You are a helpful assistant.",
        "model": { "provider": "openai", "model": "gpt-4o-mini" },
        "elevenlabsVoiceId": "optional-voice-id-for-tts",
        "tools": []
      }
    }
    Supported model providers: openai, anthropic, google, ollama
    """
    try:
        account_id = int(jwt['id']) if isinstance(jwt['id'], str) else jwt['id']
        account = db.query(Account).filter(Account.id == account_id).first()

        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Account not found"
            )

        agent_name = request_body.name.strip()
        if not agent_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Agent name cannot be empty"
            )

        config_version = request_body.config.get("version")
        if config_version != 4:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only config version 4 is supported."
            )

        try:
            validate_against_schema(request_body.config, "agent_config", 4)
        except JsonSchemaValidationError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Agent config failed validation (schema 'agent_config' v4).",
            )
        except FileNotFoundError as e:
            import logging as _log
            _log.getLogger(__name__).warning("[CREATE AGENT] Config schema file not found: %s", e)

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
        raise handle_db_error(e, "[CREATE AGENT VALUE ERROR]")
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[ERROR CREATING AGENT]")
