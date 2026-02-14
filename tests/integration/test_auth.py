"""Integration tests: Auth endpoints."""

import pytest
from tests.conftest import requires_db

pytestmark = requires_db
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_contact_inquiry_success(async_client: AsyncClient, api_base: str, unique_suffix: str):
    resp = await async_client.post(
        f"{api_base}/auth/contact-inquiry",
        json={
            "school_name": f"School {unique_suffix}",
            "email": f"inquiry_{unique_suffix}@test.com",
            "inquiry_type": "demo_request",
            "message": "Requesting a demo",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "id" in data["data"]


@pytest.mark.asyncio
async def test_contact_inquiry_validation_error(async_client: AsyncClient, api_base: str):
    resp = await async_client.post(
        f"{api_base}/auth/contact-inquiry",
        json={
            "school_name": "Test",
            "email": "invalid-email",
            "inquiry_type": "billing",
            "message": "Hi",
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_school_success(async_client: AsyncClient, api_base: str, unique_suffix: str):
    resp = await async_client.post(
        f"{api_base}/auth/register/school",
        json={
            "email": f"reg_{unique_suffix}@test.com",
            "password": "SecurePass123!",
            "school_name": f"School {unique_suffix}",
        },
    )
    assert resp.status_code == 200
    assert "school_id" in resp.json()["data"]


@pytest.mark.asyncio
async def test_register_school_duplicate_email(
    async_client: AsyncClient, api_base: str, unique_suffix: str
):
    email = f"dup_{unique_suffix}@test.com"
    await async_client.post(
        f"{api_base}/auth/register/school",
        json={"email": email, "password": "Pass123!", "school_name": "School 1"},
    )
    resp = await async_client.post(
        f"{api_base}/auth/register/school",
        json={"email": email, "password": "Pass123!", "school_name": "School 2"},
    )
    assert resp.status_code == 400
    assert "already exists" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_login_success(async_client: AsyncClient, api_base: str, registered_school: dict):
    resp = await async_client.post(
        f"{api_base}/auth/login",
        json={
            "email": registered_school["admin_email"],
            "password": registered_school["password"],
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "access_token" in data
    assert data["role"] == "school_admin"
    assert "school_id" in data


@pytest.mark.asyncio
async def test_login_wrong_password(
    async_client: AsyncClient, api_base: str, registered_school: dict
):
    resp = await async_client.post(
        f"{api_base}/auth/login",
        json={
            "email": registered_school["admin_email"],
            "password": "WrongPassword123!",
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_verify_code_invalid(async_client: AsyncClient, api_base: str):
    resp = await async_client.post(
        f"{api_base}/auth/verify-code",
        json={"access_code": "INVALID-CODE-123"},
    )
    assert resp.status_code == 400
