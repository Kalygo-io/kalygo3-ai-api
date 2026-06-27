"""
Contract test for the canonical agent access-control rule.

`src/services/agent_access.py` is byte-identical across ai-api and agent-api
(enforced by repo-root check-schemas.sh). This test is the *behavioral* half of
that guarantee: it proves the rule actually behaves the same. The agent-api copy
(tests/test_agent_access_contract.py there) exercises the identical scenarios —
keep the two in sync when adding cases.
"""
import pytest

from src.db.models import (
    Account,
    Agent,
    AccessGroup,
    AccessGroupMember,
    AgentAccessGrant,
)
from src.services.agent_access import (
    can_access_agent,
    get_accessible_agent_ids,
    load_agent_with_access_check,
)

OWNER, MEMBER, OUTSIDER, MEMBER_NOGRANT = 1001, 1002, 1003, 1004
AGENT_ID = 2001
GROUP_GRANTED, GROUP_UNGRANTED = 3001, 3002
MISSING_AGENT_ID = 999999


@pytest.fixture()
def seed(db):
    """Owner-owned agent shared with GROUP_GRANTED; a second ungranted group."""
    for acc_id, email in [
        (OWNER, "owner@example.com"),
        (MEMBER, "member@example.com"),
        (OUTSIDER, "outsider@example.com"),
        (MEMBER_NOGRANT, "member-nogrant@example.com"),
    ]:
        db.add(Account(id=acc_id, email=email))
    db.add(Agent(id=AGENT_ID, account_id=OWNER, name="SOP Agent", config={"data": {}}))
    db.add(AccessGroup(id=GROUP_GRANTED, name="Granted", owner_account_id=OWNER))
    db.add(AccessGroup(id=GROUP_UNGRANTED, name="Ungranted", owner_account_id=OWNER))
    db.add(AccessGroupMember(access_group_id=GROUP_GRANTED, account_id=MEMBER))
    db.add(AccessGroupMember(access_group_id=GROUP_UNGRANTED, account_id=MEMBER_NOGRANT))
    db.add(AgentAccessGrant(agent_id=AGENT_ID, access_group_id=GROUP_GRANTED))
    db.flush()
    return db


def test_owner_can_access(seed):
    assert can_access_agent(seed, OWNER, AGENT_ID)


def test_member_of_granted_group_can_access(seed):
    assert can_access_agent(seed, MEMBER, AGENT_ID)


def test_member_of_ungranted_group_cannot_access(seed):
    assert not can_access_agent(seed, MEMBER_NOGRANT, AGENT_ID)


def test_outsider_cannot_access(seed):
    assert not can_access_agent(seed, OUTSIDER, AGENT_ID)


def test_missing_agent_is_denied(seed):
    assert not can_access_agent(seed, OWNER, MISSING_AGENT_ID)


def test_get_accessible_agent_ids(seed):
    # Only group grants count — owner access is NOT included here.
    assert get_accessible_agent_ids(seed, MEMBER) == {AGENT_ID}
    assert get_accessible_agent_ids(seed, OWNER) == set()
    assert get_accessible_agent_ids(seed, OUTSIDER) == set()
    assert get_accessible_agent_ids(seed, MEMBER_NOGRANT) == set()


def test_load_agent_with_access_check(seed):
    assert load_agent_with_access_check(seed, OWNER, AGENT_ID).id == AGENT_ID
    assert load_agent_with_access_check(seed, MEMBER, AGENT_ID).id == AGENT_ID
    assert load_agent_with_access_check(seed, OUTSIDER, AGENT_ID) is None
    assert load_agent_with_access_check(seed, OWNER, MISSING_AGENT_ID) is None
