"""
Agent access control (thin compatibility layer over the unified resolver).

Access is now stored as AccessGrant rows and resolved by services/access.py. This
module keeps the original agent-centric helpers so existing call sites are
unchanged; each delegates to access.py with resource_type='agent', role='use'.

CANONICAL FILE. This module is mirrored byte-for-byte into kalygo3-agent-api
(src/services/agent_access.py). The ai-api copy is canonical; keep them in sync via
the repo-root scripts (./sync-schemas.sh).

Access rule: an account can access an agent if it owns the agent OR holds (directly
or via a group) an AccessGrant on it.
"""
from sqlalchemy.orm import Session

from src.db.models import Agent
from src.services import access


def can_access_agent(db: Session, account_id: int, agent_id: int) -> bool:
    """Return True if the account can view/use the agent."""
    return access.can_access(db, account_id, access.AGENT, agent_id, required="use")


def get_accessible_agent_ids(db: Session, account_id: int) -> set:
    """Agent IDs the account can access via grants (excludes owned)."""
    return access.accessible_resource_ids(db, account_id, access.AGENT, required="use")


def load_agent_with_access_check(
    db: Session,
    account_id: int,
    agent_id: int,
) -> "Agent | None":
    """Load and return the agent if *account_id* has access, else None."""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if agent is None:
        return None
    if agent.account_id == account_id:
        return agent
    return agent if can_access_agent(db, account_id, agent_id) else None
