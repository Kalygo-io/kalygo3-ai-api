"""
List agents granted to an access group (owner or member).
"""
from fastapi import APIRouter, HTTPException, status, Request
from typing import List
from src.deps import db_dependency, jwt_dependency, account_id_from_claims
from src.db.models import AccessGroup, AccessGroupMember, AccessGrant, Agent
from src.services import access
from .models import GroupAgentResponse
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

router = APIRouter()

@router.get("/{group_id}/agents", response_model=List[GroupAgentResponse])
@limiter.limit("30/minute")
async def list_group_agents(
    group_id: int,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request,
):
    """
    List the agents that have been granted to this access group.

    Accessible by the group owner or any member (mirrors list_members), so a
    member can see which agents their group membership gives them access to.
    """
    try:
        account_id = account_id_from_claims(jwt)

        group = db.query(AccessGroup).filter(AccessGroup.id == group_id).first()
        if not group:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Access group not found")

        # Owner or member?
        is_owner = group.owner_account_id == account_id
        if not is_owner:
            is_member = (
                db.query(AccessGroupMember)
                .filter(
                    AccessGroupMember.access_group_id == group_id,
                    AccessGroupMember.account_id == account_id,
                )
                .first()
                is not None
            )
            if not is_member:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Access group not found")

        rows = (
            db.query(AccessGrant, Agent.name)
            .join(Agent, Agent.id == AccessGrant.resource_id)
            .filter(
                AccessGrant.resource_type == access.AGENT,
                AccessGrant.principal_type == access.GROUP,
                AccessGrant.principal_id == group_id,
            )
            .order_by(AccessGrant.created_at.desc())
            .all()
        )

        return [
            GroupAgentResponse(
                agent_id=grant.resource_id,
                agent_name=name,
                granted_at=grant.created_at,
            )
            for grant, name in rows
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise handle_db_error(e, "[LIST GROUP AGENTS]")
