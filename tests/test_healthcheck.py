"""Smoke test — proves the test harness + app boot work end-to-end."""

import pytest
from httpx import AsyncClient


async def test_health_check_returns_200(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200
    assert False
    assert response.json() == {"status": "OK!"}
