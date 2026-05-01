"""Integration tests: Arena management endpoints (teacher console).

All endpoints require teacher auth; operations are scoped to arenas for classes
the teacher teaches. Assert observable outcomes only.

These tests run against the live core service (CORE_SERVICE_URL) since arena
CRUD endpoints (/arenas, /arenas/{id}) are served by core, not the arena microservice.
"""

import pytest
from httpx import AsyncClient

from ..conftest import FAKE_CLASS_ID


@pytest.fixture
def teacher_with_class(teacher_headers: dict) -> dict:
    """Teacher auth headers and a fixed class_id.

    Arena CRUD is owned by core; we use a fixed class UUID that the mock
    core API accepts. Tests that need the class to actually exist should
    use requires_live_server and hit the real core service.
    """
    return {"headers": teacher_headers, "class_id": FAKE_CLASS_ID}


# --- Auth ---


@pytest.mark.asyncio
async def test_list_arenas_requires_auth(async_client: AsyncClient, api_base: str):
    resp = await async_client.get(f"{api_base}/arenas")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_create_arena_requires_auth(async_client: AsyncClient, api_base: str):
    resp = await async_client.post(
        f"{api_base}/arenas",
        json={
            "class_id": "00000000-0000-0000-0000-000000000001",
            "title": "Test Arena",
            "criteria": {"Pronunciation": 50, "Fluency": 50},
        },
    )
    assert resp.status_code in (401, 403)


# --- List ---


@pytest.mark.asyncio
async def test_list_arenas_success(
    async_client: AsyncClient, api_base: str, teacher_headers: dict
):
    resp = await async_client.get(f"{api_base}/arenas", headers=teacher_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "data" in data
    assert "meta" in data
    assert isinstance(data["data"], list)


# --- Create / get / update ---


@pytest.mark.asyncio
async def test_create_arena_success(
    async_client: AsyncClient, api_base: str, teacher_with_class: dict
):
    class_id = teacher_with_class["class_id"]
    headers = teacher_with_class["headers"]
    resp = await async_client.post(
        f"{api_base}/arenas",
        headers=headers,
        json={
            "class_id": class_id,
            "title": "Speaking Challenge",
            "description": "Weekly fluency round",
            "criteria": {"Pronunciation": 40, "Fluency": 60},
            "rules": ["Speak for at least 60 seconds.", "No reading from script."],
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("success") is True
    arena = body["data"]
    assert arena["title"] == "Speaking Challenge"
    assert arena["status"] == "draft"
    assert arena["class_id"] == class_id
    assert len(arena["criteria"]) == 2
    assert len(arena["rules"]) == 2
    arena_id = arena["id"]

    resp2 = await async_client.get(f"{api_base}/arenas/{arena_id}", headers=headers)
    assert resp2.status_code == 200
    assert resp2.json()["data"]["id"] == arena_id


@pytest.mark.asyncio
async def test_create_arena_forbidden_when_not_teaching_class(
    async_client: AsyncClient, api_base: str, teacher_headers: dict
):
    resp = await async_client.post(
        f"{api_base}/arenas",
        headers=teacher_headers,
        json={
            "class_id": "00000000-0000-0000-0000-000000000099",
            "title": "Other Class Arena",
            "criteria": {"Pronunciation": 100},
        },
    )
    assert resp.status_code in (403, 404), resp.text


@pytest.mark.asyncio
async def test_get_arena_404_when_not_found(
    async_client: AsyncClient, api_base: str, teacher_headers: dict
):
    resp = await async_client.get(
        f"{api_base}/arenas/00000000-0000-0000-0000-000000000001",
        headers=teacher_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_arena_success(
    async_client: AsyncClient, api_base: str, teacher_with_class: dict
):
    class_id = teacher_with_class["class_id"]
    headers = teacher_with_class["headers"]
    create = await async_client.post(
        f"{api_base}/arenas",
        headers=headers,
        json={
            "class_id": class_id,
            "title": "Draft Arena",
            "criteria": {"A": 50, "B": 50},
            "rules": [],
        },
    )
    assert create.status_code == 200, create.text
    arena_id = create.json()["data"]["id"]

    patch = await async_client.patch(
        f"{api_base}/arenas/{arena_id}",
        headers=headers,
        json={"title": "Updated Arena Title", "description": "Updated description"},
    )
    assert patch.status_code == 200
    assert patch.json()["data"]["title"] == "Updated Arena Title"
    assert patch.json()["data"]["description"] == "Updated description"


@pytest.mark.asyncio
async def test_update_arena_404_when_not_found(
    async_client: AsyncClient, api_base: str, teacher_headers: dict
):
    resp = await async_client.patch(
        f"{api_base}/arenas/00000000-0000-0000-0000-000000000001",
        headers=teacher_headers,
        json={"title": "No"},
    )
    assert resp.status_code == 404
