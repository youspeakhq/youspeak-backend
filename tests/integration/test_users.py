"""Integration tests: Users endpoints."""

import pytest
from tests.conftest import requires_db

pytestmark = requires_db
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_users_admin(
    async_client: AsyncClient, api_base: str, registered_school: dict
):
    """Admin can list all users in the school."""
    resp = await async_client.get(
        f"{api_base}/users",
        headers=registered_school["headers"],
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "data" in data
    assert isinstance(data["data"], list)
    assert "meta" in data





# --- Delete my account (self-service) ---


@pytest.mark.asyncio
async def test_delete_my_account_requires_auth(async_client: AsyncClient, api_base: str):
    """DELETE /users/me without token returns 401 or 403."""
    resp = await async_client.request(
        "DELETE",
        f"{api_base}/users/me",
        json={"password": "any"},
    )
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_delete_my_account_wrong_password(
    async_client: AsyncClient, api_base: str, registered_school: dict
):
    """DELETE /users/me with wrong password returns 400."""
    resp = await async_client.request(
        "DELETE",
        f"{api_base}/users/me",
        headers=registered_school["headers"],
        json={"password": "WrongPassword123!"},
    )
    assert resp.status_code == 400
    assert "password" in resp.json().get("detail", "").lower() or "incorrect" in resp.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_delete_my_account_success(
    async_client: AsyncClient, api_base: str, unique_suffix: str
):
    """DELETE /users/me with correct password deletes account and returns success."""
    email = f"delete_me_{unique_suffix}@test.example.com"
    password = "DeleteMePass123!"
    reg = await async_client.post(
        f"{api_base}/auth/register/school",
        json={
            "email": email,
            "password": password,
            "school_name": f"Delete Me School {unique_suffix}",
        },
    )
    assert reg.status_code == 200, reg.text
    login = await async_client.post(
        f"{api_base}/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200, login.text
    token = login.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = await async_client.request(
        "DELETE",
        f"{api_base}/users/me",
        headers=headers,
        json={"password": password},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "deleted" in (data.get("message") or "").lower()

    # Same token should no longer be valid (user deleted)
    get_resp = await async_client.get(f"{api_base}/users", headers=headers)
    assert get_resp.status_code in (401, 403, 404)


# --- Update user name tests ---


@pytest.mark.asyncio
async def test_update_user_full_name(
    async_client: AsyncClient, api_base: str, registered_school: dict
):
    """Update user with full_name splits into first_name and last_name."""
    user_id = registered_school["user_id"]
    headers = registered_school["headers"]

    # Update with full_name
    resp = await async_client.put(
        f"{api_base}/users/{user_id}",
        headers=headers,
        json={"full_name": "John Smith"}
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["first_name"] == "John"
    assert data["last_name"] == "Smith"
    assert data["full_name"] == "John Smith"


@pytest.mark.asyncio
async def test_update_user_single_name(
    async_client: AsyncClient, api_base: str, registered_school: dict
):
    """Update user with single name sets first_name and empty last_name."""
    user_id = registered_school["user_id"]
    headers = registered_school["headers"]

    resp = await async_client.put(
        f"{api_base}/users/{user_id}",
        headers=headers,
        json={"full_name": "Madonna"}
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["first_name"] == "Madonna"
    assert data["last_name"] == ""


@pytest.mark.asyncio
async def test_update_user_multiple_names(
    async_client: AsyncClient, api_base: str, registered_school: dict
):
    """Update user with multiple names: first word is first_name, rest is last_name."""
    user_id = registered_school["user_id"]
    headers = registered_school["headers"]

    resp = await async_client.put(
        f"{api_base}/users/{user_id}",
        headers=headers,
        json={"full_name": "Mary Jane Watson"}
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["first_name"] == "Mary"
    assert data["last_name"] == "Jane Watson"


@pytest.mark.asyncio
async def test_update_user_first_last_directly(
    async_client: AsyncClient, api_base: str, registered_school: dict
):
    """Update user with first_name and last_name directly."""
    user_id = registered_school["user_id"]
    headers = registered_school["headers"]

    resp = await async_client.put(
        f"{api_base}/users/{user_id}",
        headers=headers,
        json={"first_name": "Alice", "last_name": "Wonder"}
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["first_name"] == "Alice"
    assert data["last_name"] == "Wonder"
    assert data["full_name"] == "Alice Wonder"


@pytest.mark.asyncio
async def test_update_user_whitespace_handling(
    async_client: AsyncClient, api_base: str, registered_school: dict
):
    """Update user with extra whitespace is handled correctly."""
    user_id = registered_school["user_id"]
    headers = registered_school["headers"]

    resp = await async_client.put(
        f"{api_base}/users/{user_id}",
        headers=headers,
        json={"full_name": "  Bob   Builder  "}
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["first_name"] == "Bob"
    assert data["last_name"] == "Builder"


@pytest.mark.asyncio
async def test_update_user_name_with_email_password(
    async_client: AsyncClient, api_base: str, unique_suffix: str
):
    """Update user name, email, and password together works correctly."""
    # Register new user
    email = f"multiupdate_{unique_suffix}@test.com"
    password = "OldPassword123!"
    reg = await async_client.post(
        f"{api_base}/auth/register/school",
        json={
            "email": email,
            "password": password,
            "school_name": f"Multi Update School {unique_suffix}",
        },
    )
    assert reg.status_code == 200, reg.text

    # Login
    login = await async_client.post(
        f"{api_base}/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200, login.text
    token = login.json()["data"]["access_token"]
    user_id = login.json()["data"]["user_id"]
    headers = {"Authorization": f"Bearer {token}"}

    # Update all fields
    new_email = f"updated_{unique_suffix}@test.com"
    new_password = "NewPassword456!"
    resp = await async_client.put(
        f"{api_base}/users/{user_id}",
        headers=headers,
        json={
            "full_name": "Updated Name",
            "email": new_email,
            "password": new_password
        }
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["first_name"] == "Updated"
    assert data["last_name"] == "Name"
    assert data["email"] == new_email

    # Verify new credentials work
    login2 = await async_client.post(
        f"{api_base}/auth/login",
        json={"email": new_email, "password": new_password},
    )
    assert login2.status_code == 200, login2.text
