"""
Centralized agent access control.

Single source of truth for "can this account access this agent?"

CANONICAL FILE. This module is mirrored byte-for-byte into kalygo3-agent-api
(src/services/agent_access.py). The ai-api copy is canonical; the agent-api copy
is kept in sync by the repo-root scripts (schema-files.sh / check-schemas.sh /
sync-schemas.sh). Edit the ai-api copy, then run ./sync-schemas.sh. Do not edit
the two copies independently.

Access rule:
  An account can access an agent if EITHER
    1. it owns the agent (agent.account_id == account_id), OR
    2. it is a member of at least one access group that has been granted
       access to the agent.
"""
from sqlalchemy.orm import Session
from sqlalchemy import exists, and_
from src.db.models import Agent, AgentAccessGrant, AccessGroupMember


def can_access_agent(db: Session, account_id: int, agent_id: int) -> bool:
    """
    Return True if the account can view/use the agent.

    At most two fast, index-friendly queries: a PK lookup for ownership, then
    (if not owner) a single indexed EXISTS for a group grant + membership.
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


def load_agent_with_access_check(
    db: Session,
    account_id: int,
    agent_id: int,
) -> "Agent | None":
    """
    Load and return the agent if *account_id* has access, else None.

    Convenience wrapper so the completion flow can get the Agent object and do
    the access check in one call without running the agent lookup twice. Applies
    the exact same rule as can_access_agent.
    """
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if agent is None:
        return None

    # Owner short-circuit
    if agent.account_id == account_id:
        return agent

    # Group grant check (single indexed query)
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
