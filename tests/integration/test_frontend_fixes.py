import pytest
from httpx import AsyncClient
from uuid import UUID
from tests.conftest import requires_db

pytestmark = requires_db

@pytest.mark.asyncio
async def test_batch_team_creation_success(
    async_client: AsyncClient,
    api_base: str,
    teacher_with_class_and_students: dict,
):
    """Test creating multiple teams in one batch."""
    headers = teacher_with_class_and_students["headers"]
    class_id = teacher_with_class_and_students["class_id"]
    student_ids = teacher_with_class_and_students["student_ids"]
    
    # Create a collaborative arena first
    arena_resp = await async_client.post(
        f"{api_base}/arenas",
        headers=headers,
        json={
            "class_id": class_id,
            "title": "Collaborative Challenge",
            "criteria": {"Teamwork": 100},
        },
    )
    assert arena_resp.status_code == 200
    arena_id = arena_resp.json()["data"]["id"]
    
    # Initialize it to collaborative mode
    await async_client.post(
        f"{api_base}/arenas/{arena_id}/initialize",
        headers=headers,
        json={
            "arena_mode": "collaborative",
            "judging_mode": "teacher_only",
            "student_selection_mode": "manual",
            "selected_student_ids": student_ids,
            "team_size": 2
        }
    )

    # Batch create 2 teams
    batch_resp = await async_client.post(
        f"{api_base}/arenas/{arena_id}/teams/batch",
        headers=headers,
        json={
            "teams": [
                {"team_name": "Team Alpha", "student_ids": [student_ids[0]], "leader_id": student_ids[0]},
                {"team_name": "Team Beta", "student_ids": [student_ids[1], student_ids[2]]}
            ]
        }
    )
    assert batch_resp.status_code == 200, batch_resp.text
    data = batch_resp.json()["data"]
    assert data["success"] is True
    assert len(data["created_teams"]) == 2
    assert data["created_teams"][0]["team_name"] == "Team Alpha"
    assert data["created_teams"][1]["team_name"] == "Team Beta"

@pytest.mark.asyncio
async def test_batch_team_creation_validation_duplicate_names(
    async_client: AsyncClient,
    api_base: str,
    teacher_with_class_and_students: dict,
):
    """Test batch creation fails if team names are duplicated in the batch."""
    headers = teacher_with_class_and_students["headers"]
    class_id = teacher_with_class_and_students["class_id"]
    student_ids = teacher_with_class_and_students["student_ids"]
    
    arena_resp = await async_client.post(
        f"{api_base}/arenas",
        headers=headers,
        json={"class_id": class_id, "title": "Batch Name Test", "criteria": {"A": 100}},
    )
    arena_id = arena_resp.json()["data"]["id"]
    await async_client.post(
        f"{api_base}/arenas/{arena_id}/initialize",
        headers=headers,
        json={
            "arena_mode": "collaborative",
            "judging_mode": "teacher_only",
            "student_selection_mode": "manual",
            "selected_student_ids": student_ids,
            "team_size": 2
        }
    )

    batch_resp = await async_client.post(
        f"{api_base}/arenas/{arena_id}/teams/batch",
        headers=headers,
        json={
            "teams": [
                {"team_name": "Same Name", "student_ids": [student_ids[0]]},
                {"team_name": "Same Name", "student_ids": [student_ids[1]]}
            ]
        }
    )
    assert batch_resp.status_code == 400
    assert "Duplicate team names" in batch_resp.json()["detail"]

@pytest.mark.asyncio
async def test_batch_team_creation_validation_duplicate_students(
    async_client: AsyncClient,
    api_base: str,
    teacher_with_class_and_students: dict,
):
    """Test batch creation fails if students are duplicated across teams in the batch."""
    headers = teacher_with_class_and_students["headers"]
    class_id = teacher_with_class_and_students["class_id"]
    student_ids = teacher_with_class_and_students["student_ids"]
    
    arena_resp = await async_client.post(
        f"{api_base}/arenas",
        headers=headers,
        json={"class_id": class_id, "title": "Batch Student Test", "criteria": {"A": 100}},
    )
    arena_id = arena_resp.json()["data"]["id"]
    await async_client.post(
        f"{api_base}/arenas/{arena_id}/initialize",
        headers=headers,
        json={
            "arena_mode": "collaborative",
            "judging_mode": "teacher_only",
            "student_selection_mode": "manual",
            "selected_student_ids": student_ids,
            "team_size": 2
        }
    )

    batch_resp = await async_client.post(
        f"{api_base}/arenas/{arena_id}/teams/batch",
        headers=headers,
        json={
            "teams": [
                {"team_name": "Team 1", "student_ids": [student_ids[0]]},
                {"team_name": "Team 2", "student_ids": [student_ids[0]]}
            ]
        }
    )
    assert batch_resp.status_code == 400
    assert "Duplicate student IDs" in batch_resp.json()["detail"]

@pytest.mark.asyncio
async def test_curriculum_merge_proposal_teacher_permission(
    async_client: AsyncClient,
    api_base: str,
    teacher_headers: dict,
):
    """Test that a teacher can propose a curriculum merge (formerly admin only)."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    
    # We expect 404 (because the ID is fake) but NOT 403 (Forbidden)
    resp = await async_client.post(
        f"{api_base}/curriculums/{fake_id}/merge/propose",
        headers=teacher_headers,
        json={"library_curriculum_id": fake_id}
    )
    
    assert resp.status_code == 404
    # The curriculum proxy wraps errors in a standardized ErrorResponse
    assert resp.json()["error"]["message"] != "Admin access required"
