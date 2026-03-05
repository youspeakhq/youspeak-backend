"""Integration tests: Assessment management endpoints (teacher console).

Required behavior: All endpoints require teacher auth; operations are scoped to the
current teacher's assignments, questions, and submissions. Assert observable outcomes
only: HTTP status, response JSON shape and values.
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
    """Teacher auth headers and a class_id for associating assessments."""
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
            "name": f"Assessment Class {unique_suffix}",
            "schedule": [{"day_of_week": "Mon", "start_time": "09:00:00", "end_time": "10:00:00"}],
            "language_id": 1,
            "term_id": term_id,
        },
    )
    assert resp.status_code == 200, resp.text
    class_id = resp.json()["data"]["id"]
    return {"headers": teacher_headers, "class_id": class_id}


# --- Auth: endpoints require teacher ---


@pytest.mark.asyncio
async def test_analytics_summary_requires_auth(async_client: AsyncClient, api_base: str):
    resp = await async_client.get(f"{api_base}/assessments/analytics/summary")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_list_assessments_requires_auth(async_client: AsyncClient, api_base: str):
    resp = await async_client.get(f"{api_base}/assessments")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_create_assessment_requires_auth(async_client: AsyncClient, api_base: str):
    resp = await async_client.post(
        f"{api_base}/assessments",
        json={"title": "Test", "type": "oral", "class_ids": []},
    )
    assert resp.status_code in (401, 403)


# --- Analytics summary ---


@pytest.mark.asyncio
async def test_analytics_summary_success(
    async_client: AsyncClient, api_base: str, teacher_headers: dict
):
    resp = await async_client.get(
        f"{api_base}/assessments/analytics/summary",
        headers=teacher_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data.get("success") is True
    body = data["data"]
    assert "total_assessments" in body
    assert "total_assignments" in body
    assert isinstance(body["total_assessments"], int)
    assert isinstance(body["total_assignments"], int)


# --- List / create / get / update assessments ---


@pytest.mark.asyncio
async def test_list_assessments_success(
    async_client: AsyncClient, api_base: str, teacher_headers: dict
):
    resp = await async_client.get(
        f"{api_base}/assessments",
        headers=teacher_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "data" in data
    assert "meta" in data
    assert isinstance(data["data"], list)
    meta = data["meta"]
    assert "page" in meta
    assert "page_size" in meta
    assert "total" in meta


@pytest.mark.asyncio
async def test_create_assessment_success(
    async_client: AsyncClient, api_base: str, teacher_with_class: dict, unique_suffix: str
):
    resp = await async_client.post(
        f"{api_base}/assessments",
        headers=teacher_with_class["headers"],
        json={
            "title": f"Oral Test {unique_suffix}",
            "type": "oral",
            "instructions": "Answer aloud.",
            "class_ids": [teacher_with_class["class_id"]],
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data.get("success") is True
    body = data["data"]
    assert body["title"] == f"Oral Test {unique_suffix}"
    assert body["type"] == "oral"
    assert body["status"] == "draft"
    assert "id" in body


@pytest.mark.asyncio
async def test_create_assessment_invalid_type_returns_422(
    async_client: AsyncClient, api_base: str, teacher_headers: dict
):
    resp = await async_client.post(
        f"{api_base}/assessments",
        headers=teacher_headers,
        json={"title": "Bad", "type": "invalid_type", "class_ids": []},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_assessment_with_questions(
    async_client: AsyncClient, api_base: str, teacher_with_class: dict, unique_suffix: str
):
    """Create assessment with optional questions; GET assignment questions returns them with points."""
    headers = teacher_with_class["headers"]
    q_resp = await async_client.post(
        f"{api_base}/assessments/questions/bank",
        headers=headers,
        json={
            "question_text": f"What is 2+2? {unique_suffix}",
            "type": "multiple_choice",
            "correct_answer": "4",
        },
    )
    assert q_resp.status_code == 200, q_resp.text
    question_id = q_resp.json()["data"]["id"]
    create = await async_client.post(
        f"{api_base}/assessments",
        headers=headers,
        json={
            "title": f"Quiz with Q {unique_suffix}",
            "type": "written",
            "class_ids": [teacher_with_class["class_id"]],
            "questions": [{"question_id": question_id, "points": 3}],
        },
    )
    assert create.status_code == 200, create.text
    assignment_id = create.json()["data"]["id"]
    list_q = await async_client.get(
        f"{api_base}/assessments/{assignment_id}/questions",
        headers=headers,
    )
    assert list_q.status_code == 200, list_q.text
    items = list_q.json()["data"]
    assert len(items) == 1
    assert items[0]["question"]["id"] == question_id
    assert items[0]["points"] == 3


@pytest.mark.asyncio
async def test_create_assessment_invalid_question_ids_returns_400(
    async_client: AsyncClient, api_base: str, teacher_with_class: dict
):
    """Create assessment with non-owned/invalid question_ids returns 400."""
    resp = await async_client.post(
        f"{api_base}/assessments",
        headers=teacher_with_class["headers"],
        json={
            "title": "Bad questions",
            "type": "written",
            "class_ids": [],
            "questions": [
                {"question_id": "00000000-0000-0000-0000-000000000001", "points": 1}
            ],
        },
    )
    assert resp.status_code == 400
    assert "question" in resp.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_create_assessment_with_empty_questions(
    async_client: AsyncClient, api_base: str, teacher_with_class: dict, unique_suffix: str
):
    """Create assessment with questions: [] succeeds; GET questions returns empty list."""
    create = await async_client.post(
        f"{api_base}/assessments",
        headers=teacher_with_class["headers"],
        json={
            "title": f"Empty Q {unique_suffix}",
            "type": "written",
            "class_ids": [],
            "questions": [],
        },
    )
    assert create.status_code == 200, create.text
    assignment_id = create.json()["data"]["id"]
    list_q = await async_client.get(
        f"{api_base}/assessments/{assignment_id}/questions",
        headers=teacher_with_class["headers"],
    )
    assert list_q.status_code == 200
    assert list_q.json()["data"] == []


@pytest.mark.asyncio
async def test_create_assessment_duplicate_question_ids_returns_400(
    async_client: AsyncClient, api_base: str, teacher_with_class: dict, unique_suffix: str
):
    """Create assessment with duplicate question_id in questions list returns 400."""
    headers = teacher_with_class["headers"]
    q_resp = await async_client.post(
        f"{api_base}/assessments/questions/bank",
        headers=headers,
        json={
            "question_text": f"Duplicate Q {unique_suffix}",
            "type": "multiple_choice",
            "correct_answer": "A",
        },
    )
    assert q_resp.status_code == 200
    question_id = q_resp.json()["data"]["id"]
    resp = await async_client.post(
        f"{api_base}/assessments",
        headers=headers,
        json={
            "title": "Dup",
            "type": "written",
            "class_ids": [],
            "questions": [
                {"question_id": question_id, "points": 1},
                {"question_id": question_id, "points": 2},
            ],
        },
    )
    assert resp.status_code == 400
    assert "duplicate" in resp.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_get_assessment_success(
    async_client: AsyncClient, api_base: str, teacher_with_class: dict, unique_suffix: str
):
    create = await async_client.post(
        f"{api_base}/assessments",
        headers=teacher_with_class["headers"],
        json={
            "title": f"Get Me {unique_suffix}",
            "type": "written",
            "class_ids": [teacher_with_class["class_id"]],
        },
    )
    assert create.status_code == 200, create.text
    assignment_id = create.json()["data"]["id"]
    resp = await async_client.get(
        f"{api_base}/assessments/{assignment_id}",
        headers=teacher_with_class["headers"],
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["id"] == assignment_id
    assert resp.json()["data"]["title"] == f"Get Me {unique_suffix}"


@pytest.mark.asyncio
async def test_get_assessment_not_found_returns_404(
    async_client: AsyncClient, api_base: str, teacher_headers: dict
):
    resp = await async_client.get(
        f"{api_base}/assessments/00000000-0000-0000-0000-000000000001",
        headers=teacher_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_assessment_success(
    async_client: AsyncClient, api_base: str, teacher_with_class: dict, unique_suffix: str
):
    create = await async_client.post(
        f"{api_base}/assessments",
        headers=teacher_with_class["headers"],
        json={
            "title": f"Original {unique_suffix}",
            "type": "oral",
            "class_ids": [],
        },
    )
    assert create.status_code == 200, create.text
    assignment_id = create.json()["data"]["id"]
    resp = await async_client.patch(
        f"{api_base}/assessments/{assignment_id}",
        headers=teacher_with_class["headers"],
        json={"title": f"Updated {unique_suffix}", "instructions": "New instructions"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["title"] == f"Updated {unique_suffix}"
    assert resp.json()["data"]["instructions"] == "New instructions"


# --- Question bank ---


@pytest.mark.asyncio
async def test_list_question_bank_requires_auth(async_client: AsyncClient, api_base: str):
    resp = await async_client.get(f"{api_base}/assessments/questions/bank")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_list_question_bank_success(
    async_client: AsyncClient, api_base: str, teacher_headers: dict
):
    resp = await async_client.get(
        f"{api_base}/assessments/questions/bank",
        headers=teacher_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "data" in data
    assert "meta" in data
    assert isinstance(data["data"], list)


@pytest.mark.asyncio
async def test_create_question_success(
    async_client: AsyncClient, api_base: str, teacher_headers: dict, unique_suffix: str
):
    resp = await async_client.post(
        f"{api_base}/assessments/questions/bank",
        headers=teacher_headers,
        json={
            "question_text": f"What is 2+2? {unique_suffix}",
            "type": "open_text",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data.get("success") is True
    body = data["data"]
    assert "id" in body
    assert body["question_text"] == f"What is 2+2? {unique_suffix}"
    assert body["type"] == "open_text"


@pytest.mark.asyncio
async def test_create_question_invalid_type_returns_422(
    async_client: AsyncClient, api_base: str, teacher_headers: dict
):
    resp = await async_client.post(
        f"{api_base}/assessments/questions/bank",
        headers=teacher_headers,
        json={"question_text": "Q", "type": "invalid"},
    )
    assert resp.status_code == 422


# --- Assignment questions ---


@pytest.mark.asyncio
async def test_get_assignment_questions_success(
    async_client: AsyncClient, api_base: str, teacher_with_class: dict, unique_suffix: str
):
    create = await async_client.post(
        f"{api_base}/assessments",
        headers=teacher_with_class["headers"],
        json={"title": f"A {unique_suffix}", "type": "oral", "class_ids": []},
    )
    assert create.status_code == 200, create.text
    assignment_id = create.json()["data"]["id"]
    resp = await async_client.get(
        f"{api_base}/assessments/{assignment_id}/questions",
        headers=teacher_with_class["headers"],
    )
    assert resp.status_code == 200, resp.text
    assert isinstance(resp.json()["data"], list)


@pytest.mark.asyncio
async def test_set_assignment_questions_success(
    async_client: AsyncClient,
    api_base: str,
    teacher_with_class: dict,
    teacher_headers: dict,
    unique_suffix: str,
):
    """PUT assignment questions then GET returns the same questions with points."""
    q = await async_client.post(
        f"{api_base}/assessments/questions/bank",
        headers=teacher_headers,
        json={"question_text": f"Q for assignment {unique_suffix}", "type": "open_text"},
    )
    assert q.status_code == 200, q.text
    question_id = q.json()["data"]["id"]
    create = await async_client.post(
        f"{api_base}/assessments",
        headers=teacher_with_class["headers"],
        json={"title": f"B {unique_suffix}", "type": "written", "class_ids": []},
    )
    assert create.status_code == 200, create.text
    assignment_id = create.json()["data"]["id"]
    resp = await async_client.put(
        f"{api_base}/assessments/{assignment_id}/questions",
        headers=teacher_with_class["headers"],
        json=[{"question_id": question_id, "points": 2}],
    )
    assert resp.status_code == 200, resp.text
    get_q = await async_client.get(
        f"{api_base}/assessments/{assignment_id}/questions",
        headers=teacher_with_class["headers"],
    )
    assert get_q.status_code == 200, get_q.text
    items = get_q.json()["data"]
    assert len(items) == 1, get_q.text
    assert items[0]["points"] == 2
    assert items[0]["question"]["question_text"] == f"Q for assignment {unique_suffix}"


# --- Submissions ---


@pytest.mark.asyncio
async def test_list_submissions_success(
    async_client: AsyncClient, api_base: str, teacher_with_class: dict, unique_suffix: str
):
    create = await async_client.post(
        f"{api_base}/assessments",
        headers=teacher_with_class["headers"],
        json={"title": f"C {unique_suffix}", "type": "oral", "class_ids": []},
    )
    assert create.status_code == 200, create.text
    assignment_id = create.json()["data"]["id"]
    resp = await async_client.get(
        f"{api_base}/assessments/{assignment_id}/submissions",
        headers=teacher_with_class["headers"],
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "data" in data
    assert "meta" in data
    assert isinstance(data["data"], list)


@pytest.mark.asyncio
async def test_list_submissions_not_found_returns_404(
    async_client: AsyncClient, api_base: str, teacher_headers: dict
):
    resp = await async_client.get(
        f"{api_base}/assessments/00000000-0000-0000-0000-000000000001/submissions",
        headers=teacher_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_submission_not_found_returns_404(
    async_client: AsyncClient, api_base: str, teacher_with_class: dict, unique_suffix: str
):
    create = await async_client.post(
        f"{api_base}/assessments",
        headers=teacher_with_class["headers"],
        json={"title": f"D {unique_suffix}", "type": "oral", "class_ids": []},
    )
    assert create.status_code == 200, create.text
    assignment_id = create.json()["data"]["id"]
    resp = await async_client.get(
        f"{api_base}/assessments/{assignment_id}/submissions/00000000-0000-0000-0000-000000000002",
        headers=teacher_with_class["headers"],
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_grade_submission_not_found_returns_404(
    async_client: AsyncClient, api_base: str, teacher_with_class: dict, unique_suffix: str
):
    create = await async_client.post(
        f"{api_base}/assessments",
        headers=teacher_with_class["headers"],
        json={"title": f"E {unique_suffix}", "type": "oral", "class_ids": []},
    )
    assert create.status_code == 200, create.text
    assignment_id = create.json()["data"]["id"]
    resp = await async_client.patch(
        f"{api_base}/assessments/{assignment_id}/submissions/00000000-0000-0000-0000-000000000002/grade",
        headers=teacher_with_class["headers"],
        json={"teacher_score": 85.5, "status": "graded"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_assessment_with_alignment_fields(
    async_client: AsyncClient, api_base: str, teacher_headers: dict, class_id_for_student: str, unique_suffix: str
):
    """Verify that an assessment can be created with topics and rubric data (Figma Alignment)."""
    topics = ["Vocabulary: Morning Routine", "Grammar: Reflexive Verbs"]
    rubric_url = "https://storage.youspeak.com/rubrics/french_101.pdf"
    rubric_data = [
        {"criterion": "Pronunciation", "max_points": 10, "description": "Clarity of speech"},
        {"criterion": "Grammar", "max_points": 5, "description": "Correct use of reflexive verbs"}
    ]
    
    resp = await async_client.post(
        f"{api_base}/assessments",
        headers=teacher_headers,
        json={
            "title": f"Aligned Assessment {unique_suffix}",
            "type": "oral",
            "instructions": "Speak clearly into the microphone.",
            "class_ids": [class_id_for_student],
            "topics": topics,
            "rubric_url": rubric_url,
            "rubric_data": rubric_data
        },
    )
    
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["topics"] == topics
    assert data["rubric_url"] == rubric_url
    assert len(data["rubric_data"]) == 2


@pytest.mark.asyncio
async def test_create_question_with_true_false_type(
    async_client: AsyncClient, api_base: str, teacher_headers: dict, unique_suffix: str
):
    """Verify that a TRUE_FALSE question can be created (Figma Alignment)."""
    resp = await async_client.post(
        f"{api_base}/assessments/questions/bank",
        headers=teacher_headers,
        json={
            "question_text": f"Is 'Bonjour' a morning greeting? {unique_suffix}",
            "type": "true_false",
            "correct_answer": "true"
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["type"] == "true_false"
