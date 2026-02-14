"""E2E tests: Full school onboarding flow."""

import pytest
from tests.conftest import requires_db

pytestmark = requires_db
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_contact_inquiry_then_register_and_login(
    async_client: AsyncClient, api_base: str, unique_suffix: str
):
    """
    E2E: Submit contact inquiry (optional step), register school, login, fetch profile.
    """
    school_name = f"E2E School {unique_suffix}"
    email = f"school_{unique_suffix}@test.example.com"

    # 1. Contact inquiry (pre-onboarding)
    resp = await async_client.post(
        f"{api_base}/auth/contact-inquiry",
        json={
            "school_name": school_name,
            "email": email,
            "inquiry_type": "new_onboarding",
            "message": "Interested in onboarding",
        },
    )
    assert resp.status_code == 200
    assert "id" in resp.json()["data"]

    # 2. Register school (full onboarding payload)
    resp = await async_client.post(
        f"{api_base}/auth/register/school",
        json={
            "email": email,
            "password": "SecurePass123!",
            "school_name": school_name,
            "school_type": "secondary",
            "program_type": "pioneer",
            "address_country": "United States",
            "address_state": "CA",
            "address_city": "Los Angeles",
            "address_zip": "90001",
            "languages": ["es", "fr"],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "school_id" in data["data"]

    # 3. Login
    resp = await async_client.post(
        f"{api_base}/auth/login",
        json={"email": email, "password": "SecurePass123!"},
    )
    assert resp.status_code == 200
    token = resp.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 4. Fetch school profile
    resp = await async_client.get(f"{api_base}/schools/profile", headers=headers)
    assert resp.status_code == 200
    profile = resp.json()["data"]
    assert profile["name"] == school_name
    assert profile["address_country"] == "United States"
    assert profile["address_city"] == "Los Angeles"


@pytest.mark.asyncio
async def test_minimal_register_login_profile(
    async_client: AsyncClient, api_base: str, unique_suffix: str
):
    """
    E2E: Minimal registration (email, password, school_name only), login, profile.
    """
    email = f"minimal_{unique_suffix}@test.example.com"
    school_name = f"Minimal School {unique_suffix}"

    resp = await async_client.post(
        f"{api_base}/auth/register/school",
        json={
            "email": email,
            "password": "Pass123!",
            "school_name": school_name,
        },
    )
    assert resp.status_code == 200

    resp = await async_client.post(
        f"{api_base}/auth/login",
        json={"email": email, "password": "Pass123!"},
    )
    assert resp.status_code == 200
    headers = {"Authorization": f"Bearer {resp.json()['data']['access_token']}"}

    resp = await async_client.get(f"{api_base}/schools/profile", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == school_name
