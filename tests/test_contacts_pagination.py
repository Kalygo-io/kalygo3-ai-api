"""Server-side pagination contract for GET /api/contacts/.

Asserts the envelope shape ({contacts,total,limit,offset,has_more}), the
limit/offset slice, server-side search, and account isolation.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session

from src.db.models import Account, Contact

CONTACTS_URL = "/api/contacts/"


@pytest.fixture()
def seed_contacts(db: Session, test_account: Account):
    for i in range(57):
        db.add(
            Contact(
                account_id=test_account.id,
                first_name=f"Person{i:03d}",
                last_name="Test",
                email=f"person{i:03d}@example.com",
            )
        )
    # A different account's contact must never appear.
    other = Account(id=2, email="other@example.com")
    db.add(other)
    db.flush()
    db.add(
        Contact(
            account_id=other.id,
            first_name="Foreign",
            last_name="Person",
            email="foreign@example.com",
        )
    )
    db.flush()


async def test_envelope_shape_and_default_page(
    authed_client: AsyncClient, seed_contacts
):
    resp = await authed_client.get(CONTACTS_URL)
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) >= {"contacts", "total", "limit", "offset", "has_more"}
    assert body["total"] == 57          # excludes the other account's contact
    assert body["limit"] == 50
    assert body["offset"] == 0
    assert len(body["contacts"]) == 50
    assert body["has_more"] is True


async def test_offset_limit_slice_and_last_page(
    authed_client: AsyncClient, seed_contacts
):
    resp = await authed_client.get(CONTACTS_URL, params={"limit": 25, "offset": 50})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 57
    assert body["limit"] == 25
    assert body["offset"] == 50
    assert len(body["contacts"]) == 7   # 57 - 50
    assert body["has_more"] is False


async def test_search_filters_server_side(
    authed_client: AsyncClient, seed_contacts
):
    resp = await authed_client.get(CONTACTS_URL, params={"search": "person001"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["contacts"][0]["email"] == "person001@example.com"


async def test_limit_is_capped(authed_client: AsyncClient, seed_contacts):
    # Backend Query(le=500): an over-large limit is rejected as 422.
    resp = await authed_client.get(CONTACTS_URL, params={"limit": 99999})
    assert resp.status_code == 422
