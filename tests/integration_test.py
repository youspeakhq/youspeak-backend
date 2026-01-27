import asyncio
import httpx
import pytest
from app.config import settings

# Base URL for API
BASE_URL = "http://localhost:8000/api/v1"

@pytest.mark.asyncio
async def test_full_onboarding_flow():
    """
    Test the complete onboarding flow:
    1. Register a new school
    2. Register a teacher (via access code - mocked for now or requiring admin to generate)
    3. Login as Admin
    4. Fetch Profile
    """
    
    # unique emails for this run
    import uuid
    run_id = str(uuid.uuid4())[:8]
    admin_email = f"admin_{run_id}@example.com"
    school_name = f"Test School {run_id}"
    
    async with httpx.AsyncClient() as client:
        # 1. Register School
        print(f"\n[1] Registering School: {school_name}")
        try:
            response = await client.post(
                f"{BASE_URL}/auth/register/school",
                json={
                    "account_type": "school",
                    "email": admin_email,
                    "password": "StrongPassword123!",
                    "school_name": school_name,
                    "admin_first_name": "Admin",
                    "admin_last_name": "User"
                }
            )
            print(f"Status: {response.status_code}")
            if response.status_code != 200:
                print(f"Error Body: {response.text}")
            assert response.status_code == 200
            data = response.json()
            assert data.get("success") is True, f"Success flag not true: {data}"
            school_id = data["data"]["school_id"]
            print(f"    -> Success! School ID: {school_id}")
            
            # 2. Login as Admin
            print(f"\n[2] Logging in as Admin: {admin_email}")
            response = await client.post(
                f"{BASE_URL}/auth/login",
                json={
                    "email": admin_email,
                    "password": "StrongPassword123!"
                }
            )
            if response.status_code != 200:
                print(f"Login Error: {response.text}")
            assert response.status_code == 200
            data = response.json()
            token = data["data"]["access_token"]
            print(f"    -> Success! Token received")
            
            # 3. Get School Profile
            print(f"\n[3] Fetching School Profile")
            headers = {"Authorization": f"Bearer {token}"}
            response = await client.get(
                f"{BASE_URL}/schools/profile",
                headers=headers
            )
            if response.status_code != 200:
                print(f"Profile Error: {response.text}")
            assert response.status_code == 200
            data = response.json()
            fetched_name = data["data"]["name"]
            assert fetched_name == school_name
            print(f"    -> Success! Profile matches: {fetched_name}")
            
        except Exception as e:
            print(f"Inner Exception: {e}")
            raise

if __name__ == "__main__":
    # If run directly as script
    try:
        asyncio.run(test_full_onboarding_flow())
        print("\n✅ All tests passed!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        # Print full response if available in exception for better debugging
