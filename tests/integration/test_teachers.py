"""Integration tests: Teachers endpoints."""

import pytest
from tests.conftest import requires_db

pytestmark = requires_db
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_teachers(
    async_client: AsyncClient, api_base: str, registered_school: dict
):
    resp = await async_client.get(
        f"{api_base}/teachers",
        headers=registered_school["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "data" in data
    assert "meta" in data


@pytest.mark.asyncio
async def test_create_teacher_invite(
    async_client: AsyncClient, api_base: str, registered_school: dict, unique_suffix: str
):
    """Admin creates teacher (is_active=False); code sent via email. Teacher activates with code."""
    resp = await async_client.post(
        f"{api_base}/teachers",
        headers=registered_school["headers"],
        json={
            "first_name": "New",
            "last_name": "Teacher",
            "email": f"newteacher_{unique_suffix}@test.com",
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "access_code" in data
    assert "teacher_id" in data


@pytest.mark.asyncio
async def test_import_teachers_csv(
    async_client: AsyncClient,
    api_base: str,
    registered_school: dict,
    unique_suffix: str,
):
    """Bulk import teachers from CSV."""
    csv_content = (
        f"first_name,last_name,email\n"
        f"Bulk,One,bulk1_{unique_suffix}@test.com\n"
        f"Bulk,Two,bulk2_{unique_suffix}@test.com\n"
    ).encode("utf-8")
    resp = await async_client.post(
        f"{api_base}/teachers/import",
        headers=registered_school["headers"],
        files={"file": ("teachers.csv", csv_content, "text/csv")},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["created"] == 2
    assert "invitations" in data
    assert len(data["invitations"]) == 2


@pytest.mark.asyncio
async def test_import_teachers_csv_rejects_non_csv(
    async_client: AsyncClient, api_base: str, registered_school: dict
):
    """Import rejects non-CSV files."""
    resp = await async_client.post(
        f"{api_base}/teachers/import",
        headers=registered_school["headers"],
        files={"file": ("data.txt", b"not csv", "text/plain")},
    )
    assert resp.status_code == 400
