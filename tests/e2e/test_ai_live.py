import pytest
from httpx import AsyncClient
from app.config import settings
import os

@pytest.mark.asyncio
async def test_live_bedrock_generation(async_client: AsyncClient, api_base: str, registered_school: dict):
    """
    E2E test that hits the real AWS Bedrock (Claude 3) to generate a curriculum.
    NO MOCKS ALLOWED.
    """
    # Ensure we are NOT in test mode where AI is skipped
    os.environ["TEST_MODE"] = "false"
    
    headers = registered_school["headers"]
    payload = {
        "prompt": "Create a 5-day intensive crash course for Japanese travel phrases for beginners.",
        "language_id": 1 # English (assuming it exists in DB)
    }

    print(f"\n[LIVE TEST] Sending request to {api_base}/curriculums/generate with Bedrock...")
    
    resp = await async_client.post(
        f"{api_base}/curriculums/generate",
        headers=headers,
        json=payload
    )

    # Log response for proof
    print(f"[LIVE TEST] Response status: {resp.status_code}")
    if resp.status_code != 200:
        print(f"[LIVE TEST] Error body: {resp.text}")
    
    assert resp.status_code == 200
    
    data = resp.json()["data"]
    assert len(data) > 0
    
    print(f"[LIVE TEST] Successfully generated {len(data)} topics via Claude 3 (Bedrock).")
    for i, topic in enumerate(data[:3]):
        print(f"  Topic {i+1}: {topic['title']} ({topic['duration_hours']} hours)")
        if "learning_objectives" in topic:
            print(f"    Objectives: {topic['learning_objectives']}")

@pytest.mark.asyncio
async def test_live_bedrock_extraction(async_client: AsyncClient, api_base: str, registered_school: dict):
    """
    E2E test that hits the real AWS Bedrock to extract topics from a PDF.
    Uses a local file path to avoid SSL/DNS issues in the test environment.
    """
    os.environ["TEST_MODE"] = "false"
    headers = registered_school["headers"]
    
    # Create a local dummy PDF
    local_pdf_path = "/tmp/test_syllabus.pdf"
    with open(local_pdf_path, "wb") as f:
        f.write(b"%PDF-1.4\n1 0 obj\n<< /Title (Test Syllabus) /Creator (Test) >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF")
    
    # Create curriculum
    upload_resp = await async_client.post(
        f"{api_base}/curriculums",
        headers=headers,
        data={"title": "Local E2E Syllabus", "language_id": "1"},
        files={"file": ("dummy.pdf", b"%PDF-1.4", "application/pdf")}
    )
    assert upload_resp.status_code == 200
    curriculum_id = upload_resp.json()["data"]["id"]
    
    # Patch the curriculum to point to the local file path
    # The service extract_topics handles paths that don't start with 'http'
    patch_resp = await async_client.patch(
        f"{api_base}/curriculums/{curriculum_id}",
        headers=headers,
        json={"file_url": local_pdf_path}
    )
    assert patch_resp.status_code == 200
    
    print(f"\n[LIVE TEST] Triggering extraction for curriculum {curriculum_id} from {local_pdf_path}...")
    
    extract_resp = await async_client.post(
        f"{api_base}/curriculums/{curriculum_id}/extract",
        headers=headers
    )
    
    print(f"[LIVE TEST] Extraction response: {extract_resp.status_code}")
    if extract_resp.status_code != 200:
        print(f"[LIVE TEST] Error: {extract_resp.text}")
        
    assert extract_resp.status_code == 200
    topics = extract_resp.json()["data"]
    print(f"[LIVE TEST] Extraction finished. Found {len(topics)} topics via Bedrock.")
    if len(topics) > 0:
        print(f"  First extracted Topic: {topics[0]['title']}")
    
    # Cleanup
    if os.path.exists(local_pdf_path):
        os.remove(local_pdf_path)
