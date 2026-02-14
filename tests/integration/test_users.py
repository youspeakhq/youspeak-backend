"""Integration tests: Users endpoints."""

import pytest
from tests.conftest import requires_db

pytestmark = requires_db
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_users_admin(
    async_client: AsyncClient, api_base: str, registered_school: dict
):
    # Users router: /api/v1/users (include) + /users (router prefix) = /users/users
    resp = await async_client.get(
        f"{api_base}/users/users",
        headers=registered_school["headers"],
    )
    if resp.status_code == 404:
        resp = await async_client.get(
            f"{api_base}/users",
            headers=registered_school["headers"],
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data or "data" in data
