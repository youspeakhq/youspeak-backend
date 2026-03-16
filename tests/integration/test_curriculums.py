"""Integration tests for curriculum API. Core API proxies to curriculum service; these tests hit the proxy."""

import os
import pytest
from httpx import AsyncClient
from uuid import UUID
from unittest.mock import patch

from tests.conftest import requires_db

pytestmark = requires_db

# Skip curriculum upload tests when R2 is not configured (CI, local without R2)
requires_r2 = pytest.mark.skipif(
    not all(
        os.getenv(k)
        for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY")
    ),
    reason="R2 storage not configured (set R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY)",
)


class _MockCurriculumResponse:
    def __init__(self, status_code: int, json_data: dict = None, text: str = ""):
        self.status_code = status_code
        self._json = json_data if json_data is not None else {}
        self.text = text or ""

    def json(self):
        return self._json


class _MockCurriculumHttpClient:
    """Mock curriculum service HTTP client: returns 404 for all requests (for proxy tests that expect 404)."""

    async def get(self, url, params=None, headers=None, **kwargs):
        return _MockCurriculumResponse(404, {"detail": "Not found"})

    async def post(self, url, json=None, data=None, headers=None, **kwargs):
        return _MockCurriculumResponse(404, {"detail": "Not found"})

    async def patch(self, url, json=None, headers=None, **kwargs):
        return _MockCurriculumResponse(404, {"detail": "Not found"})

    async def delete(self, url, **kwargs):
        return _MockCurriculumResponse(404, {"detail": "Not found"})


@pytest.fixture
def mock_curriculum_service_404():
    """Patch proxy's curriculum client so it returns 404 (for tests that only need 404 from proxy)."""
    mock_client = _MockCurriculumHttpClient()
    with patch("app.api.v1.endpoints.curriculums._get_curriculum_client", return_value=mock_client):
        yield

@requires_r2
@pytest.mark.skipif(
    not os.getenv("CURRICULUM_SERVICE_URL"),
    reason="CURRICULUM_SERVICE_URL required (proxy needs curriculum service)",
)
@pytest.mark.asyncio
async def test_curriculum_lifecycle(
    async_client: AsyncClient,
    api_base: str,
    registered_school: dict,
    unique_suffix: str,
):
    """Test full lifecycle of a curriculum: upload, list, update, merge, delete."""
    headers = registered_school["headers"]
    
    # 1. Create a classroom and class for assignment
    cr_resp = await async_client.post(
        f"{api_base}/classrooms",
        headers=headers,
        json={"name": f"CurriculumRoom {unique_suffix}", "language_id": 1, "level": "a1"},
    )
    assert cr_resp.status_code == 200
    classroom_id = cr_resp.json()["data"]["id"]
    
    # Get active semester
    # (Assuming school fixture handles this or we hit an endpoint to find it)
    # For now, we'll create one if needed, but let's try to get my classes first
    class_name = f"CurriculumClass {unique_suffix}"
    
    # We need a semester ID. Let's look for one or create one.
    # In this backend, we might need to create it.
    sem_resp = await async_client.post(
        f"{api_base}/admin/activity", # Placeholder for actual semester creation if it exists
        headers=headers,
        # Mocking or finding semester is complex here, let's assume we can list classes if any exist
    )
    
    # Actually, let's just test the curriculum upload without class assignment first to be safe, 
    # then test assignment if we can find a class.
    
    # 2. Upload Curriculum (Multipart)
    file_content = b"test curriculum content"
    files = {
        "file": ("curriculum.pdf", file_content, "application/pdf")
    }
    data = {
        "title": f"Test Curriculum {unique_suffix}",
        "language_id": "1",
        "description": "Integration testing curriculum"
    }
    
    resp = await async_client.post(
        f"{api_base}/curriculums",
        headers=headers,
        data=data,
        files=files
    )
    assert resp.status_code == 200, resp.text
    curriculum = resp.json()["data"]
    curriculum_id = curriculum["id"]
    assert curriculum["title"] == data["title"]
    assert "language_name" in curriculum
    
    # 3. List Curriculums
    list_resp = await async_client.get(f"{api_base}/curriculums", headers=headers)
    assert list_resp.status_code == 200
    items = list_resp.json()["data"]
    assert any(c["id"] == curriculum_id for c in items)
    
    # 4. Update Curriculum (Status to ARCHIVED)
    update_resp = await async_client.patch(
        f"{api_base}/curriculums/{curriculum_id}",
        headers=headers,
        json={"status": "archived"}
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["data"]["status"] == "archived"
    
    # 5. Extract Topics
    extract_resp = await async_client.post(
        f"{api_base}/curriculums/{curriculum_id}/extract",
        headers=headers
    )
    assert extract_resp.status_code == 200
    topics = extract_resp.json()["data"]
    assert len(topics) > 0
    topic_id = topics[0]["id"]
    
    # 5a. Update Topic
    topic_update_resp = await async_client.patch(
        f"{api_base}/curriculums/topics/{topic_id}",
        headers=headers,
        json={"title": "Updated Topic Title"}
    )
    assert topic_update_resp.status_code == 200
    assert topic_update_resp.json()["data"]["title"] == "Updated Topic Title"

    # 6. Merge Curriculum (Confirm)
    confirm_data = {"final_topics": extract_resp.json()["data"]}
    merge_resp = await async_client.post(
        f"{api_base}/curriculums/{curriculum_id}/merge/confirm",
        headers=headers,
        json=confirm_data
    )
    assert merge_resp.status_code == 200
    assert "Integrated Edition" in merge_resp.json()["data"]["title"]
    
    # 6. Delete Curriculum
    del_resp = await async_client.delete(f"{api_base}/curriculums/{curriculum_id}", headers=headers)
    assert del_resp.status_code == 200
    
    # Verify gone
    get_resp = await async_client.get(f"{api_base}/curriculums/{curriculum_id}", headers=headers)
    assert get_resp.status_code == 404

@pytest.mark.asyncio
async def test_curriculum_not_found_scenarios(
    async_client: AsyncClient,
    api_base: str,
    registered_school: dict,
    mock_curriculum_service_404,
):
    """Test that all endpoints properly return 404 when curriculum service returns 404 (proxy forwards)."""
    headers = registered_school["headers"]
    fake_uuid = "00000000-0000-0000-0000-000000000000"
    
    # Get 404
    resp = await async_client.get(f"{api_base}/curriculums/{fake_uuid}", headers=headers)
    assert resp.status_code == 404
    
    # Update 404
    resp = await async_client.patch(f"{api_base}/curriculums/{fake_uuid}", headers=headers, json={"title": "New"})
    assert resp.status_code == 404
    
    # Extract 404
    resp = await async_client.post(f"{api_base}/curriculums/{fake_uuid}/extract", headers=headers)
    assert resp.status_code == 404
    
    # Merge Propose 404
    resp = await async_client.post(
        f"{api_base}/curriculums/{fake_uuid}/merge/propose", 
        headers=headers,
        json={"library_curriculum_id": fake_uuid}
    )
    assert resp.status_code == 404
    
    # Merge Confirm 404
    resp = await async_client.post(
        f"{api_base}/curriculums/{fake_uuid}/merge/confirm", 
        headers=headers,
        json={"final_topics": []}
    )
    assert resp.status_code == 404 # It will fail finding base curriculum

    # Delete 404
    resp = await async_client.delete(f"{api_base}/curriculums/{fake_uuid}", headers=headers)
    assert resp.status_code == 404

    # Update Topic 404
    resp = await async_client.patch(f"{api_base}/curriculums/topics/{fake_uuid}", headers=headers, json={"title": "New"})
    assert resp.status_code == 404

@requires_r2
@pytest.mark.skipif(
    not os.getenv("CURRICULUM_SERVICE_URL"),
    reason="CURRICULUM_SERVICE_URL required (proxy needs curriculum service)",
)
@pytest.mark.asyncio
async def test_curriculum_merge_proposal(
    async_client: AsyncClient,
    api_base: str,
    registered_school: dict,
    unique_suffix: str,
):
    """Test generating a merge proposal between a teacher upload and a library item."""
    headers = registered_school["headers"]
    
    # Upload Curriculum 1 (Teacher)
    files1 = {"file": ("c1.pdf", b"test", "application/pdf")}
    data1 = {"title": f"Teacher Curric {unique_suffix}", "language_id": "1"}
    resp1 = await async_client.post(f"{api_base}/curriculums", headers=headers, data=data1, files=files1)
    teacher_curriculum_id = resp1.json()["data"]["id"]
    
    # Extract topics to populate the teacher curriculum
    await async_client.post(f"{api_base}/curriculums/{teacher_curriculum_id}/extract", headers=headers)

    # Upload Curriculum 2 (Library Mock)
    files2 = {"file": ("c2.pdf", b"test", "application/pdf")}
    data2 = {"title": f"Library Curric {unique_suffix}", "language_id": "1"}
    resp2 = await async_client.post(f"{api_base}/curriculums", headers=headers, data=data2, files=files2)
    library_curriculum_id = resp2.json()["data"]["id"]
    
    # Test Propose Merge
    propose_resp = await async_client.post(
        f"{api_base}/curriculums/{teacher_curriculum_id}/merge/propose",
        headers=headers,
        json={"library_curriculum_id": library_curriculum_id}
    )
    assert propose_resp.status_code == 200
    
    data = propose_resp.json()["data"]
    assert "proposal_id" in data
    assert "proposed_topics" in data
    
    # The mock returns 1 blended topic if the teacher curriculum has topics
    assert len(data["proposed_topics"]) == 1
    assert data["proposed_topics"][0]["action"] == "blend"

@pytest.mark.skipif(
    not os.getenv("RUN_LIVE_E2E"),
    reason="Curriculum generation uses Bedrock; set RUN_LIVE_E2E=1 to run",
)
@pytest.mark.skipif(
    not os.getenv("CURRICULUM_SERVICE_URL"),
    reason="CURRICULUM_SERVICE_URL required (proxy needs curriculum service)",
)
@pytest.mark.asyncio
async def test_curriculum_generation(
    async_client: AsyncClient,
    api_base: str,
    registered_school: dict,
):
    """Test generating curriculum topics from a prompt (live Bedrock)."""
    headers = registered_school["headers"]
    generate_data = {"prompt": "Learn French for travelers", "language_id": 1}
    resp = await async_client.post(
        f"{api_base}/curriculums/generate",
        headers=headers,
        json=generate_data,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert isinstance(data, list)
    assert len(data) >= 1
    assert "title" in data[0] and "id" in data[0]
