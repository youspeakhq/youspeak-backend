"""Integration tests: References endpoints (public)."""

import random
import string

import pytest
from tests.conftest import requires_db

pytestmark = requires_db
from httpx import AsyncClient

# Reserved codes (seed data); we skip these when assigning unique codes.
_RESERVED_LANGUAGE_CODES = {"en", "es", "fr"}


def _random_language_code() -> str:
    """Random 2-letter code (a-z), not in reserved set."""
    while True:
        code = random.choice(string.ascii_lowercase) + random.choice(string.ascii_lowercase)
        if code not in _RESERVED_LANGUAGE_CODES:
            return code


@pytest.fixture
def unique_language_code() -> str:
    """Per-test unique 2-letter language code to avoid DB collisions (random to survive persistent DB)."""
    return _random_language_code()


async def _create_language_with_unique_code(
    async_client, api_base: str, headers: dict, name: str, max_attempts: int = 5
):
    """Create a language; on 400 'already exists' retry with a new code. Returns (name, code, response)."""
    for _ in range(max_attempts):
        code = _random_language_code()
        resp = await async_client.post(
            f"{api_base}/references/languages",
            headers=headers,
            json={"name": name, "code": code},
        )
        if resp.status_code == 201:
            return name, code, resp
        if resp.status_code != 400 or "already exists" not in (resp.json() or {}).get("error", {}).get("message", ""):
            resp.raise_for_status()
    raise AssertionError(f"Could not create language {name} after {max_attempts} attempts (duplicate code collision)")


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
async def test_create_language_success(
    async_client: AsyncClient,
    api_base: str,
    registered_school: dict,
    unique_suffix: str,
):
    """Test creating a new language with valid data. Use unique name/code to avoid conflicts."""
    name = f"German_{unique_suffix}"
    name, code, resp = await _create_language_with_unique_code(
        async_client, api_base, registered_school["headers"], name
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["name"] == name
    assert data["data"]["code"] == code
    assert "id" in data["data"]


@pytest.mark.asyncio
async def test_create_language_duplicate_code(
    async_client: AsyncClient,
    api_base: str,
    registered_school: dict,
    unique_suffix: str,
):
    """Test creating a language with duplicate code returns 400."""
    _, code, create_resp = await _create_language_with_unique_code(
        async_client, api_base, registered_school["headers"], f"Portuguese_{unique_suffix}"
    )
    assert create_resp.status_code == 201, create_resp.text
    # Try to create another with same code
    resp = await async_client.post(
        f"{api_base}/references/languages",
        headers=registered_school["headers"],
        json={"name": "Portuguese Brazil", "code": code},
    )
    assert resp.status_code == 400
    assert "already exists" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_create_language_duplicate_name(
    async_client: AsyncClient,
    api_base: str,
    registered_school: dict,
    unique_suffix: str,
):
    """Test creating a language with duplicate name returns 400."""
    name = f"Italian_{unique_suffix}"
    _, code, create_resp = await _create_language_with_unique_code(
        async_client, api_base, registered_school["headers"], name
    )
    assert create_resp.status_code == 201, create_resp.text
    second_code = _random_language_code()
    while second_code == code:
        second_code = _random_language_code()
    # Try to create another with same name (use valid 2-letter code so we get 400 for duplicate name, not 422)
    resp = await async_client.post(
        f"{api_base}/references/languages",
        headers=registered_school["headers"],
        json={"name": name, "code": second_code},
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
async def test_delete_language_unused(
    async_client: AsyncClient,
    api_base: str,
    registered_school: dict,
    unique_suffix: str,
):
    """Test deleting an unused language succeeds."""
    _, code, create_resp = await _create_language_with_unique_code(
        async_client, api_base, registered_school["headers"], f"Dutch_{unique_suffix}"
    )
    assert create_resp.status_code == 201, create_resp.text
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
    assert code not in language_codes


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
            "level": "beginner"
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
async def test_get_languages_excludes_inactive(
    async_client: AsyncClient,
    api_base: str,
    registered_school: dict,
    unique_suffix: str,
):
    """Test that GET /languages only returns active languages."""
    _, code, create_resp = await _create_language_with_unique_code(
        async_client, api_base, registered_school["headers"], f"Swedish_{unique_suffix}"
    )
    assert create_resp.status_code == 201, create_resp.text
    language_id = create_resp.json()["data"]["id"]
    
    # Verify it appears in the list
    get_resp = await async_client.get(f"{api_base}/references/languages")
    languages = get_resp.json()["data"]
    language_codes = [lang["code"] for lang in languages]
    assert code in language_codes

    # Delete it
    await async_client.delete(
        f"{api_base}/references/languages/{language_id}",
        headers=registered_school["headers"],
    )

    # Verify it no longer appears in the list
    get_resp = await async_client.get(f"{api_base}/references/languages")
    languages = get_resp.json()["data"]
    language_codes = [lang["code"] for lang in languages]
    assert code not in language_codes
