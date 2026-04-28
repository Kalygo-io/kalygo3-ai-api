"""Tests for the /api/auth endpoints and auth dependency behavior."""

import pytest
from httpx import AsyncClient

from tests.conftest import make_token


async def test_validate_token_with_valid_bearer(client: AsyncClient):
    token = make_token()
    response = await client.get(
        "/api/auth/validate-token",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert "access_token" in body


async def test_validate_token_missing_header(client: AsyncClient):
    response = await client.get("/api/auth/validate-token")
    assert response.status_code == 422


async def test_validate_token_with_expired_token(client: AsyncClient):
    token = make_token(hours=-1)
    response = await client.get(
        "/api/auth/validate-token",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401


async def test_auth_me_with_bearer_header(authed_client: AsyncClient):
    response = await authed_client.get("/api/auth/me")
    assert response.status_code == 200
    assert response.json()["email"] == "test@example.com"


async def test_auth_me_with_cookie(client: AsyncClient, auth_token: str):
    client.cookies.set("jwt", auth_token)
    response = await client.get("/api/auth/me")
    assert response.status_code == 200
    assert response.json()["email"] == "test@example.com"


async def test_auth_me_without_credentials(client: AsyncClient):
    response = await client.get("/api/auth/me")
    assert response.status_code == 401


async def test_auth_me_with_invalid_token(client: AsyncClient):
    response = await client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer not-a-real-jwt"},
    )
    assert response.status_code == 401
