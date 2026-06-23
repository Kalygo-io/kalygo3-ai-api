"""
Update agent endpoint.
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency, account_id_from_claims, ensure_account
from src.db.models import Agent
from src.schemas import validate_against_schema
from jsonschema import ValidationError as JsonSchemaValidationError
from .models import UpdateAgentRequest, AgentResponse
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

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
    Update an agent by ID (name and/or config).
    Config must be version 4 if provided.
    Only allows updating agents belonging to the authenticated user.
    """
    try:
        account_id = account_id_from_claims(jwt)
        account = ensure_account(db, account_id)

        agent = db.query(Agent).filter(
            Agent.id == agent_id,
            Agent.account_id == account_id
        ).first()

        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent not found"
            )

        if request_body.name is None and request_body.config is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one field (name or config) must be provided for update"
            )

        if request_body.name is not None:
            agent_name = request_body.name.strip()
            if not agent_name:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Agent name cannot be empty"
                )
            agent.name = agent_name

        if request_body.config is not None:
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
                _log.getLogger(__name__).warning("[UPDATE AGENT] Config schema file not found: %s", e)

            agent.config = request_body.config

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
        raise handle_db_error(e, "[UPDATE AGENT VALUE ERROR]")
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[ERROR UPDATING AGENT]")
