"""Integration tests: References endpoints (public)."""

import pytest
from tests.conftest import requires_db

pytestmark = requires_db
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_languages(async_client: AsyncClient, api_base: str):
    resp = await async_client.get(f"{api_base}/references/languages")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, list)
    # Seeded languages: en, es, fr
    assert len(data) >= 1
    for lang in data:
        assert "id" in lang
        assert "name" in lang
        assert "code" in lang


@pytest.mark.asyncio
async def test_create_language_success(async_client: AsyncClient, api_base: str, registered_school: dict):
    """Test creating a new language with valid data."""
    resp = await async_client.post(
        f"{api_base}/references/languages",
        headers=registered_school["headers"],
        json={"name": "German", "code": "de"}
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["name"] == "German"
    assert data["data"]["code"] == "de"
    assert "id" in data["data"]


@pytest.mark.asyncio
async def test_create_language_duplicate_code(async_client: AsyncClient, api_base: str, registered_school: dict):
    """Test creating a language with duplicate code returns 400."""
    # First create a language
    await async_client.post(
        f"{api_base}/references/languages",
        headers=registered_school["headers"],
        json={"name": "Portuguese", "code": "pt"}
    )
    
    # Try to create another with same code
    resp = await async_client.post(
        f"{api_base}/references/languages",
        headers=registered_school["headers"],
        json={"name": "Portuguese Brazil", "code": "pt"}
    )
    assert resp.status_code == 400
    assert "already exists" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_create_language_duplicate_name(async_client: AsyncClient, api_base: str, registered_school: dict):
    """Test creating a language with duplicate name returns 400."""
    # First create a language
    await async_client.post(
        f"{api_base}/references/languages",
        headers=registered_school["headers"],
        json={"name": "Italian", "code": "it"}
    )
    
    # Try to create another with same name
    resp = await async_client.post(
        f"{api_base}/references/languages",
        headers=registered_school["headers"],
        json={"name": "Italian", "code": "ita"}
    )
    assert resp.status_code == 400
    assert "already exists" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_create_language_invalid_code_format(async_client: AsyncClient, api_base: str, registered_school: dict):
    """Test creating a language with invalid code format returns 422."""
    # Test uppercase code
    resp = await async_client.post(
        f"{api_base}/references/languages",
        headers=registered_school["headers"],
        json={"name": "Japanese", "code": "JP"}
    )
    assert resp.status_code == 422
    
    # Test single letter
    resp = await async_client.post(
        f"{api_base}/references/languages",
        headers=registered_school["headers"],
        json={"name": "Japanese", "code": "j"}
    )
    assert resp.status_code == 422
    
    # Test three letters
    resp = await async_client.post(
        f"{api_base}/references/languages",
        headers=registered_school["headers"],
        json={"name": "Japanese", "code": "jpn"}
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_delete_language_unused(async_client: AsyncClient, api_base: str, registered_school: dict):
    """Test deleting an unused language succeeds."""
    # Create a language
    create_resp = await async_client.post(
        f"{api_base}/references/languages",
        headers=registered_school["headers"],
        json={"name": "Dutch", "code": "nl"}
    )
    language_id = create_resp.json()["data"]["id"]
    
    # Delete it
    resp = await async_client.delete(
        f"{api_base}/references/languages/{language_id}",
        headers=registered_school["headers"]
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    
    # Verify it's not in the active list
    get_resp = await async_client.get(f"{api_base}/references/languages")
    languages = get_resp.json()["data"]
    language_codes = [lang["code"] for lang in languages]
    assert "nl" not in language_codes


@pytest.mark.asyncio
async def test_delete_language_in_use_by_school(async_client: AsyncClient, api_base: str, registered_school: dict):
    """Test deleting a language in use by a school returns 400 with counts."""
    # School is already using "es" from registration
    # Find the Spanish language ID
    get_resp = await async_client.get(f"{api_base}/references/languages")
    languages = get_resp.json()["data"]
    spanish = next(lang for lang in languages if lang["code"] == "es")
    
    # Try to delete it
    resp = await async_client.delete(
        f"{api_base}/references/languages/{spanish['id']}",
        headers=registered_school["headers"]
    )
    assert resp.status_code == 400
    error_msg = resp.json()["error"]["message"]
    assert "in use" in error_msg
    assert "school" in error_msg


@pytest.mark.asyncio
async def test_delete_language_in_use_by_classroom(
    async_client: AsyncClient, api_base: str, registered_school: dict
):
    """Test deleting a language in use by a classroom returns 400 with counts."""
    # Create a classroom with Spanish
    get_resp = await async_client.get(f"{api_base}/references/languages")
    languages = get_resp.json()["data"]
    spanish = next(lang for lang in languages if lang["code"] == "es")
    
    classroom_resp = await async_client.post(
        f"{api_base}/classrooms",
        headers=registered_school["headers"],
        json={
            "name": "Test Classroom",
            "language_id": spanish["id"],
            "proficiency_level": "beginner"
        }
    )
    assert classroom_resp.status_code in [200, 201]
    
    # Try to delete the language
    resp = await async_client.delete(
        f"{api_base}/references/languages/{spanish['id']}",
        headers=registered_school["headers"]
    )
    assert resp.status_code == 400
    error_msg = resp.json()["error"]["message"]
    assert "in use" in error_msg
    assert "classroom" in error_msg


@pytest.mark.asyncio
async def test_delete_language_not_found(async_client: AsyncClient, api_base: str, registered_school: dict):
    """Test deleting a non-existent language returns 404."""
    resp = await async_client.delete(
        f"{api_base}/references/languages/99999",
        headers=registered_school["headers"]
    )
    assert resp.status_code == 404
    assert "not found" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_get_languages_excludes_inactive(async_client: AsyncClient, api_base: str, registered_school: dict):
    """Test that GET /languages only returns active languages."""
    # Create and then delete a language
    create_resp = await async_client.post(
        f"{api_base}/references/languages",
        headers=registered_school["headers"],
        json={"name": "Swedish", "code": "sv"}
    )
    language_id = create_resp.json()["data"]["id"]
    
    # Verify it appears in the list
    get_resp = await async_client.get(f"{api_base}/references/languages")
    languages = get_resp.json()["data"]
    language_codes = [lang["code"] for lang in languages]
    assert "sv" in language_codes
    
    # Delete it
    await async_client.delete(
        f"{api_base}/references/languages/{language_id}",
        headers=registered_school["headers"]
    )
    
    # Verify it no longer appears in the list
    get_resp = await async_client.get(f"{api_base}/references/languages")
    languages = get_resp.json()["data"]
    language_codes = [lang["code"] for lang in languages]
    assert "sv" not in language_codes
