"""Integration tests: Arena management endpoints (teacher console).

All endpoints require teacher auth; operations are scoped to arenas for classes
the teacher teaches. Assert observable outcomes only.
"""

import pytest
from tests.conftest import requires_db
from httpx import AsyncClient

pytestmark = requires_db


@pytest.fixture
async def teacher_with_class(
    async_client: AsyncClient,
    api_base: str,
    teacher_headers: dict,
    unique_suffix: str,
):
    """Teacher auth headers and a class_id for creating arenas."""
    resp = await async_client.get(
        f"{api_base}/schools/terms",
        headers=teacher_headers,
    )
    assert resp.status_code == 200, resp.text
    terms = resp.json().get("data", [])
    assert terms, "Need at least one semester"
    term_id = terms[0]["id"]
    resp = await async_client.post(
        f"{api_base}/my-classes",
        headers=teacher_headers,
        json={
            "name": f"Arena Class {unique_suffix}",
            "schedule": [{"day_of_week": "Mon", "start_time": "09:00:00", "end_time": "10:00:00"}],
            "language_id": 1,
            "term_id": term_id,
        },
    )
    assert resp.status_code == 200, resp.text
    class_id = resp.json()["data"]["id"]
    return {"headers": teacher_headers, "class_id": class_id}


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


# --- List / create / get / update ---


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
    # Use a class_id the teacher does not teach (e.g. another teacher's class or random UUID)
    resp = await async_client.post(
        f"{api_base}/arenas",
        headers=teacher_headers,
        json={
            "class_id": "00000000-0000-0000-0000-000000000099",
            "title": "Other Class Arena",
            "criteria": {"Pronunciation": 100},
        },
    )
    assert resp.status_code == 403, resp.text


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
    assert create.status_code == 200
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
