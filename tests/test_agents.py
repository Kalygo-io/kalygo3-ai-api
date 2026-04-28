"""Tests for the /api/agents endpoints (CRUD cycle)."""

import pytest
from httpx import AsyncClient

VALID_AGENT_CONFIG = {
    "schema": "agent_config",
    "version": 4,
    "data": {
        "systemPrompt": "You are a test assistant.",
        "model": {"provider": "openai", "model": "gpt-4o-mini"},
        "tools": [],
    },
}


async def test_list_agents_empty(authed_client: AsyncClient):
    response = await authed_client.get("/api/agents/")
    assert response.status_code == 200
    assert response.json() == []


async def test_create_agent(authed_client: AsyncClient):
    response = await authed_client.post(
        "/api/agents/",
        json={"name": "Test Agent", "config": VALID_AGENT_CONFIG},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Test Agent"
    assert body["id"] is not None
    assert body["config"]["version"] == 4


async def test_create_and_list_agent(authed_client: AsyncClient):
    create_resp = await authed_client.post(
        "/api/agents/",
        json={"name": "Listed Agent", "config": VALID_AGENT_CONFIG},
    )
    assert create_resp.status_code == 201

    list_resp = await authed_client.get("/api/agents/")
    assert list_resp.status_code == 200
    agents = list_resp.json()
    assert len(agents) == 1
    assert agents[0]["name"] == "Listed Agent"


async def test_get_agent_by_id(authed_client: AsyncClient):
    create_resp = await authed_client.post(
        "/api/agents/",
        json={"name": "Fetchable Agent", "config": VALID_AGENT_CONFIG},
    )
    agent_id = create_resp.json()["id"]

    get_resp = await authed_client.get(f"/api/agents/{agent_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "Fetchable Agent"
    assert get_resp.json()["is_owner"] is True


async def test_get_agent_not_found(authed_client: AsyncClient):
    response = await authed_client.get("/api/agents/99999")
    assert response.status_code == 404


async def test_create_agent_unauthenticated(client: AsyncClient):
    response = await client.post(
        "/api/agents/",
        json={"name": "No Auth", "config": VALID_AGENT_CONFIG},
    )
    assert response.status_code == 401


async def test_create_agent_empty_name(authed_client: AsyncClient):
    response = await authed_client.post(
        "/api/agents/",
        json={"name": "  ", "config": VALID_AGENT_CONFIG},
    )
    assert response.status_code == 400


async def test_create_agent_invalid_config_version(authed_client: AsyncClient):
    bad_config = {**VALID_AGENT_CONFIG, "version": 2}
    response = await authed_client.post(
        "/api/agents/",
        json={"name": "Bad Config", "config": bad_config},
    )
    assert response.status_code == 400
