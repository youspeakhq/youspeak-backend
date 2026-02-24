"""Curriculum service API: list, get, create, update, delete (behavior-focused)."""

import os
import uuid
import pytest
from httpx import AsyncClient

from tests.conftest import requires_db


pytestmark = [requires_db, pytest.mark.asyncio]


async def test_list_curriculums_empty(client: AsyncClient, curriculum_headers: dict):
    """Listing curriculums with no data returns 200 and empty data array."""
    resp = await client.get("/curriculums", headers=curriculum_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "data" in data
    assert data["data"] == []
    assert data.get("meta", {}).get("total") == 0


async def test_list_curriculums_requires_school_id(client: AsyncClient):
    """Missing X-School-Id returns 422."""
    resp = await client.get("/curriculums")
    assert resp.status_code == 422


async def test_list_curriculums_invalid_school_id(client: AsyncClient):
    """Invalid X-School-Id (not a UUID) returns 400."""
    resp = await client.get(
        "/curriculums",
        headers={"X-School-Id": "not-a-uuid"},
    )
    assert resp.status_code == 400
    assert "Invalid" in resp.json().get("detail", "")


async def test_get_curriculum_not_found(client: AsyncClient, curriculum_headers: dict):
    """GET non-existent curriculum returns 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    resp = await client.get(
        f"/curriculums/{fake_id}",
        headers=curriculum_headers,
    )
    assert resp.status_code == 404
    assert "not found" in resp.json().get("detail", "").lower()


async def test_delete_curriculum_not_found(client: AsyncClient, curriculum_headers: dict):
    """DELETE non-existent curriculum returns 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    resp = await client.delete(
        f"/curriculums/{fake_id}",
        headers=curriculum_headers,
    )
    assert resp.status_code == 404


async def test_patch_curriculum_not_found(client: AsyncClient, curriculum_headers: dict):
    """PATCH non-existent curriculum returns 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    resp = await client.patch(
        f"/curriculums/{fake_id}",
        headers=curriculum_headers,
        json={"title": "New Title"},
    )
    assert resp.status_code == 404


async def test_create_curriculum_success(
    client: AsyncClient,
    existing_school_id: str,
):
    """Create curriculum with file_url returns 200 and curriculum with id and title."""
    headers = {"X-School-Id": existing_school_id}
    payload = {
        "title": "Test Curriculum",
        "language_id": 1,
        "description": "Integration test",
        "file_url": "https://example.com/doc.pdf",
        "class_ids": [],
    }
    resp = await client.post(
        "/curriculums",
        headers=headers,
        json=payload,
    )
    if resp.status_code == 500 and "language" in resp.text.lower():
        pytest.skip("Test DB has no language id=1; run core migrations first")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "data" in data
    c = data["data"]
    assert "id" in c
    assert c["title"] == payload["title"]
    assert c.get("language_name") or c.get("language_id") is not None

    # List includes the new item
    list_resp = await client.get(
        "/curriculums",
        headers=headers,
    )
    assert list_resp.status_code == 200
    items = list_resp.json()["data"]
    assert any(str(item["id"]) == str(c["id"]) for item in items)

    # Get by id returns same curriculum
    get_resp = await client.get(
        f"/curriculums/{c['id']}",
        headers=headers,
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["data"]["title"] == payload["title"]

    # Update then delete
    patch_resp = await client.patch(
        f"/curriculums/{c['id']}",
        headers=headers,
        json={"status": "archived"},
    )
    assert patch_resp.status_code == 200

    del_resp = await client.delete(
        f"/curriculums/{c['id']}",
        headers=headers,
    )
    assert del_resp.status_code == 200

    get_after = await client.get(
        f"/curriculums/{c['id']}",
        headers=headers,
    )
    assert get_after.status_code == 404
