"""
Permission-matrix tests for access-group co-admins (Tier 3 #3).

Roles: OWNER (access_groups.owner_account_id), ADMIN (member.role='admin'),
MEMBER (member.role='member'), OUTSIDER (no membership).

Verifies admins can co-manage the roster, name, and grants, while destructive /
privileged actions stay owner-only.
"""
import os
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient, ASGITransport
from jose import jwt as jose_jwt
from sqlalchemy.orm import Session

from src.db.models import Account, Agent, AccessGroup, AccessGroupMember
from src.deps import get_db
from src.main import app

OWNER, ADMIN, MEMBER, OUTSIDER, NEWHIRE, ADMIN2 = 1, 2, 3, 4, 5, 6
GROUP = 100
ADMIN_AGENT = 200   # owned by ADMIN
MEMBER_AGENT = 201  # owned by MEMBER

GROUPS_URL = "/api/access-groups"

_SECRET = os.environ["AUTH_SECRET_KEY"]
_ALG = os.environ["AUTH_ALGORITHM"]


def _auth(account_id: int, email: str) -> dict:
    token = jose_jwt.encode(
        {"sub": email, "id": account_id, "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        _SECRET,
        algorithm=_ALG,
    )
    return {"Authorization": f"Bearer {token}"}


OWNER_H = _auth(OWNER, "owner@x.com")
ADMIN_H = _auth(ADMIN, "admin@x.com")
MEMBER_H = _auth(MEMBER, "member@x.com")


@pytest.fixture()
def seed(db: Session):
    for uid, email in [
        (OWNER, "owner@x.com"), (ADMIN, "admin@x.com"), (MEMBER, "member@x.com"),
        (OUTSIDER, "outsider@x.com"), (NEWHIRE, "newhire@x.com"), (ADMIN2, "admin2@x.com"),
    ]:
        db.add(Account(id=uid, email=email))
    db.add(AccessGroup(id=GROUP, name="Employees", owner_account_id=OWNER))
    db.add(AccessGroupMember(access_group_id=GROUP, account_id=ADMIN, role="admin"))
    db.add(AccessGroupMember(access_group_id=GROUP, account_id=MEMBER, role="member"))
    db.add(AccessGroupMember(access_group_id=GROUP, account_id=ADMIN2, role="admin"))
    db.add(Agent(id=ADMIN_AGENT, account_id=ADMIN, name="Admin Agent", config={"data": {}}))
    db.add(Agent(id=MEMBER_AGENT, account_id=MEMBER, name="Member Agent", config={"data": {}}))
    db.flush()
    return db


@pytest.fixture()
async def client(_override_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ── roster management ────────────────────────────────────────────────

async def test_admin_can_add_member(client, seed):
    r = await client.post(f"{GROUPS_URL}/{GROUP}/members", json={"email": "newhire@x.com"}, headers=ADMIN_H)
    assert r.status_code == 201
    assert r.json()["role"] == "member"


async def test_member_cannot_add_member(client, seed):
    r = await client.post(f"{GROUPS_URL}/{GROUP}/members", json={"email": "newhire@x.com"}, headers=MEMBER_H)
    assert r.status_code == 403


async def test_admin_can_remove_regular_member(client, seed):
    r = await client.delete(f"{GROUPS_URL}/{GROUP}/members/{MEMBER}", headers=ADMIN_H)
    assert r.status_code == 204


async def test_admin_cannot_remove_another_admin(client, seed):
    r = await client.delete(f"{GROUPS_URL}/{GROUP}/members/{ADMIN2}", headers=ADMIN_H)
    assert r.status_code == 403


async def test_owner_can_remove_admin(client, seed):
    r = await client.delete(f"{GROUPS_URL}/{GROUP}/members/{ADMIN2}", headers=OWNER_H)
    assert r.status_code == 204


# ── rename ───────────────────────────────────────────────────────────

async def test_admin_can_rename(client, seed):
    r = await client.patch(f"{GROUPS_URL}/{GROUP}", json={"name": "Renamed"}, headers=ADMIN_H)
    assert r.status_code == 200 and r.json()["name"] == "Renamed"


async def test_member_cannot_rename(client, seed):
    r = await client.patch(f"{GROUPS_URL}/{GROUP}", json={"name": "Nope"}, headers=MEMBER_H)
    assert r.status_code == 403


# ── delete (owner only) ──────────────────────────────────────────────

async def test_admin_cannot_delete_group(client, seed):
    r = await client.delete(f"{GROUPS_URL}/{GROUP}", headers=ADMIN_H)
    assert r.status_code in (403, 404)  # delete stays owner-only


# ── promote / demote (owner only) ────────────────────────────────────

async def test_admin_cannot_promote(client, seed):
    r = await client.patch(f"{GROUPS_URL}/{GROUP}/members/{MEMBER}/role", json={"role": "admin"}, headers=ADMIN_H)
    assert r.status_code == 403


async def test_owner_can_promote_then_demote(client, seed):
    up = await client.patch(f"{GROUPS_URL}/{GROUP}/members/{MEMBER}/role", json={"role": "admin"}, headers=OWNER_H)
    assert up.status_code == 200 and up.json()["role"] == "admin"
    down = await client.patch(f"{GROUPS_URL}/{GROUP}/members/{MEMBER}/role", json={"role": "member"}, headers=OWNER_H)
    assert down.status_code == 200 and down.json()["role"] == "member"


# ── agent grants ─────────────────────────────────────────────────────

async def test_admin_can_grant_and_revoke_own_agent(client, seed):
    grant = await client.post(f"/api/agents/{ADMIN_AGENT}/access-grants", json={"accessGroupId": GROUP}, headers=ADMIN_H)
    assert grant.status_code == 201
    revoke = await client.delete(f"/api/agents/{ADMIN_AGENT}/access-grants/{GROUP}", headers=ADMIN_H)
    assert revoke.status_code == 204


async def test_plain_member_cannot_grant_to_group(client, seed):
    # MEMBER owns MEMBER_AGENT but is only a plain member of the group → group-side denial.
    r = await client.post(f"/api/agents/{MEMBER_AGENT}/access-grants", json={"accessGroupId": GROUP}, headers=MEMBER_H)
    assert r.status_code == 403
