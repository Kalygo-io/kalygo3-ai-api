"""
Centralized agent access control.

Single source of truth for "can this account access this agent?"
Used by ai-api routes and completion-api. If rules change, update here only.
"""
from sqlalchemy.orm import Session
from sqlalchemy import exists, and_
from src.db.models import Agent, AgentAccessGrant, AccessGroupMember


def can_access_agent(db: Session, account_id: int, agent_id: int) -> bool:
    """
    Return True if the account can view/use the agent.

    Access rule:
      1. Account owns the agent, OR
      2. Account is a member of at least one access group that has been
         granted access to the agent.
    """
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        return False

    # Owner always has access
    if agent.account_id == account_id:
        return True

    # Check group-based access (single indexed query)
    grant_exists = db.query(
        exists().where(
            and_(
                AgentAccessGrant.agent_id == agent_id,
                AgentAccessGrant.access_group_id == AccessGroupMember.access_group_id,
                AccessGroupMember.account_id == account_id,
            )
        )
    ).scalar()

    return grant_exists


def get_accessible_agent_ids(db: Session, account_id: int) -> set:
    """
    Return the set of agent IDs the account can access via group grants
    (does NOT include agents the account owns -- caller unions those separately).
    """
    rows = (
        db.query(AgentAccessGrant.agent_id)
        .join(
            AccessGroupMember,
            AccessGroupMember.access_group_id == AgentAccessGrant.access_group_id,
        )
        .filter(AccessGroupMember.account_id == account_id)
        .distinct()
        .all()
    )
    return {r[0] for r in rows}


def load_agent_with_access_check(db: Session, account_id: int, agent_id: int):
    """
    Load an agent only if the account is allowed to access it.

    Returns the Agent instance when the account owns it or has been granted
    access via an access group (see ``can_access_agent``); returns None when the
    agent does not exist or access is denied. This keeps the access decision and
    the load in a single call so callers cannot accidentally use an agent they
    were not authorized to see.
    """
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        return None

    # Owner always has access
    if agent.account_id == account_id:
        return agent

    # Check group-based access (single indexed query)
    grant_exists = db.query(
        exists().where(
            and_(
                AgentAccessGrant.agent_id == agent_id,
                AgentAccessGrant.access_group_id == AccessGroupMember.access_group_id,
                AccessGroupMember.account_id == account_id,
            )
        )
    ).scalar()

    return agent if grant_exists else None
