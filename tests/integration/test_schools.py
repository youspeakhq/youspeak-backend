"""Integration tests: Schools endpoints."""

import pytest
from tests.conftest import requires_db

pytestmark = requires_db
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_school_profile_requires_auth(async_client: AsyncClient, api_base: str):
    resp = await async_client.get(f"{api_base}/schools/profile")
    # FastAPI HTTPBearer returns 403 when Authorization header is missing
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_get_school_profile_success(
    async_client: AsyncClient, api_base: str, registered_school: dict
):
    resp = await async_client.get(
        f"{api_base}/schools/profile",
        headers=registered_school["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["name"] == registered_school["school_name"]
    assert "languages" in data
    assert isinstance(data["languages"], list)


@pytest.mark.asyncio
async def test_update_school_profile(
    async_client: AsyncClient, api_base: str, registered_school: dict, unique_suffix: str
):
    resp = await async_client.put(
        f"{api_base}/schools/profile",
        headers=registered_school["headers"],
        json={
            "address_country": "Canada",
            "address_state": "ON",
            "address_city": "Toronto",
            "address_zip": "M5V 1A1",
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["address_country"] == "Canada"
    assert data["address_city"] == "Toronto"


@pytest.mark.asyncio
async def test_school_profile_returns_languages_after_program_update(
    async_client: AsyncClient, api_base: str, registered_school: dict
):
    """GET /schools/profile returns current languages; updating program then profile reflects it."""
    put_resp = await async_client.put(
        f"{api_base}/schools/program",
        headers=registered_school["headers"],
        json={"languages": ["es", "fr"]},
    )
    assert put_resp.status_code == 200, put_resp.text
    get_resp = await async_client.get(
        f"{api_base}/schools/profile",
        headers=registered_school["headers"],
    )
    assert get_resp.status_code == 200
    data = get_resp.json()["data"]
    assert data["languages"] == ["es", "fr"]


@pytest.mark.asyncio
async def test_remove_school_program(
    async_client: AsyncClient, api_base: str, registered_school: dict
):
    """DELETE /schools/program/{code} removes one language; profile then reflects it."""
    await async_client.put(
        f"{api_base}/schools/program",
        headers=registered_school["headers"],
        json={"languages": ["es", "fr"]},
    )
    resp = await async_client.delete(
        f"{api_base}/schools/program/fr",
        headers=registered_school["headers"],
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["languages"] == ["es"]
    get_resp = await async_client.get(
        f"{api_base}/schools/profile",
        headers=registered_school["headers"],
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["data"]["languages"] == ["es"]


@pytest.mark.asyncio
async def test_remove_school_program_not_offered_returns_404(
    async_client: AsyncClient, api_base: str, registered_school: dict
):
    """DELETE /schools/program/{code} returns 404 when school does not offer that language."""
    await async_client.put(
        f"{api_base}/schools/program",
        headers=registered_school["headers"],
        json={"languages": ["es"]},
    )
    resp = await async_client.delete(
        f"{api_base}/schools/program/fr",
        headers=registered_school["headers"],
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_school_profile_email_and_phone(
    async_client: AsyncClient, api_base: str, registered_school: dict, unique_suffix: str
):
    """PUT /schools/profile accepts email and phone (Bio Data); GET returns them."""
    school_email = f"school_{unique_suffix}@example.com"
    school_phone = "+1-555-000-1234"
    resp = await async_client.put(
        f"{api_base}/schools/profile",
        headers=registered_school["headers"],
        json={"email": school_email, "phone": school_phone},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["email"] == school_email
    assert data["phone"] == school_phone
    get_resp = await async_client.get(
        f"{api_base}/schools/profile",
        headers=registered_school["headers"],
    )
    assert get_resp.status_code == 200
    get_data = get_resp.json()["data"]
    assert get_data["email"] == school_email
    assert get_data["phone"] == school_phone


@pytest.mark.asyncio
async def test_update_school_programs(
    async_client: AsyncClient, api_base: str, registered_school: dict
):
    resp = await async_client.put(
        f"{api_base}/schools/program",
        headers=registered_school["headers"],
        json={"languages": ["es", "fr"]},
    )
    if resp.status_code != 200:
        print(f"update_school_programs failed: status={resp.status_code} body={resp.text}")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_semesters(
    async_client: AsyncClient, api_base: str, registered_school: dict
):
    resp = await async_client.get(
        f"{api_base}/schools/semesters",
        headers=registered_school["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, list)
    assert len(data) > 0
    assert "id" in data[0]
    assert "name" in data[0]
