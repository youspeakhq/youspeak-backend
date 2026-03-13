"""
Assessment management endpoints — teacher console only.
All routes require teacher auth and operate on the current teacher's data.
"""

from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.config import settings
from app.models.user import User
from app.schemas.content import (
    AssessmentCreate,
    AssessmentUpdate,
    AssessmentResponse,
    AssessmentListRow,
    QuestionBase,
    QuestionResponse,
    AssignmentQuestionItem,
    SubmissionRow,
    SubmissionGradeUpdate,
    AnalyticsSummary,
    GenerateQuestionsRequest,
    GeneratedQuestion,
    MarkingCriterionItem,
)
from app.schemas.responses import SuccessResponse, PaginatedResponse, PaginationMeta
from app.services import storage_service as storage
from app.services.assessment_service import AssessmentService

router = APIRouter()


def _detail_from_response(r) -> str:
    if r.headers.get("content-type", "").startswith("application/json"):
        return r.json().get("detail", r.text)
    return r.text


def _assignment_to_list_row(
    a,
    class_name: Optional[str] = None,
    active_students: Optional[int] = None,
    average_score: Optional[float] = None,
) -> dict:
    return {
        "id": a.id,
        "title": a.title,
        "category": a.category,
        "type": a.type,
        "status": a.status,
        "due_date": a.due_date,
        "class_name": class_name,
        "active_students": active_students,
        "task_topic": None,
        "average_score": average_score,
        "enable_ai_marking": getattr(a, "enable_ai_marking", False),
    }


# Define /questions/bank before /{assignment_id} so "questions" is not parsed as UUID


@router.get("/questions/bank", response_model=PaginatedResponse[QuestionResponse])
async def list_question_bank(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """List teacher's question bank."""
    skip = (page - 1) * page_size
    questions, total = await AssessmentService.list_questions(db, current_user.id, skip=skip, limit=page_size)
    total_pages = (total + page_size - 1) // page_size if total else 0
    return PaginatedResponse(
        data=[QuestionResponse.model_validate(q) for q in questions],
        meta=PaginationMeta(page=page, page_size=page_size, total=total, total_pages=total_pages),
    )


@router.post("/questions/bank", response_model=SuccessResponse[QuestionResponse])
async def create_question(
    body: QuestionBase,
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """Create a question in the teacher's bank."""
    q = await AssessmentService.create_question(db, current_user.id, body)
    return SuccessResponse(data=QuestionResponse.model_validate(q), message="Question created")


@router.post("/questions/bank/bulk", response_model=SuccessResponse[List[QuestionResponse]])
async def bulk_create_questions(
    questions: List[QuestionBase],
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """Bulk create questions in the teacher's bank (for saving AI-generated questions)."""
    if not questions:
        raise HTTPException(status_code=400, detail="Questions list cannot be empty")

    created = await AssessmentService.bulk_create_questions(db, current_user.id, questions)
    return SuccessResponse(
        data=[QuestionResponse.model_validate(q) for q in created],
        message=f"{len(created)} questions saved to bank",
    )


@router.post("/questions/generate", response_model=SuccessResponse[List[GeneratedQuestion]])
async def generate_questions(
    request: Request,
    body: GenerateQuestionsRequest,
    current_user: User = Depends(deps.require_teacher),
) -> Any:
    """Generate with AI: produce assessment questions from topics (Bedrock via curriculum service)."""
    client = getattr(request.app.state, "curriculum_http", None)
    if not client:
        raise HTTPException(status_code=503, detail="Curriculum service is not configured (CURRICULUM_SERVICE_URL)")
    headers = {"X-School-Id": str(current_user.school_id)}
    if settings.CURRICULUM_INTERNAL_SECRET:
        headers["X-Internal-Secret"] = settings.CURRICULUM_INTERNAL_SECRET
    r = await client.post(
        "/curriculums/assessment-questions/generate",
        json={"topics": body.topics, "assignment_type": body.assignment_type, "num_questions": body.num_questions},
        headers=headers,
    )
    if r.status_code >= 400:
        detail = r.json().get("detail", r.text) if r.headers.get("content-type", "").startswith("application/json") else r.text
        raise HTTPException(status_code=r.status_code, detail=detail)
    data = r.json()
    questions = data.get("data", [])
    return SuccessResponse(
        data=[GeneratedQuestion(**q) for q in questions],
        message="Questions generated",
    )


def _curriculum_headers(current_user: User) -> dict:
    h = {"X-School-Id": str(current_user.school_id)}
    if settings.CURRICULUM_INTERNAL_SECRET:
        h["X-Internal-Secret"] = settings.CURRICULUM_INTERNAL_SECRET
    return h


@router.post("/questions/upload", response_model=SuccessResponse[dict])
async def upload_questions_file(
    request: Request,
    file: UploadFile = File(...),
    save_to_bank: bool = Query(False, description="Create extracted questions in teacher's bank"),
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """Upload questions manually: file → R2 → curriculum parse → extract questions. Optional save_to_bank."""
    client = getattr(request.app.state, "curriculum_http", None)
    if not client:
        raise HTTPException(status_code=503, detail="Curriculum service is not configured (CURRICULUM_SERVICE_URL)")
    content = await file.read()
    key_prefix = f"assessments/{current_user.id}/questions"
    try:
        file_url = await storage.upload(
            key_prefix,
            file.filename or "questions.pdf",
            content,
            content_type=file.content_type,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    r_parse = await client.post(
        "/curriculums/parse-document",
        json={"file_url": file_url},
        headers=_curriculum_headers(current_user),
    )
    if r_parse.status_code >= 400:
        raise HTTPException(status_code=r_parse.status_code, detail=_detail_from_response(r_parse))
    markdown = r_parse.json().get("data", {}).get("markdown", "")
    r_extract = await client.post(
        "/curriculums/extract-questions",
        json={"markdown": markdown},
        headers=_curriculum_headers(current_user),
    )
    if r_extract.status_code >= 400:
        raise HTTPException(status_code=r_extract.status_code, detail=_detail_from_response(r_extract))
    questions_data = r_extract.json().get("data", {}).get("questions", [])
    questions = [GeneratedQuestion(**q) for q in questions_data]
    question_ids: List[UUID] = []
    if save_to_bank:
        from app.models.enums import QuestionType
        for gq in questions:
            qt = (
                QuestionType(gq.type)
                if gq.type in ("multiple_choice", "open_text", "oral")
                else QuestionType.OPEN_TEXT
            )
            q = await AssessmentService.create_question(
                db, current_user.id,
                QuestionBase(question_text=gq.question_text, type=qt, correct_answer=gq.correct_answer, options=gq.options),
            )
            question_ids.append(q.id)
    return SuccessResponse(
        data={"questions": [q.model_dump() for q in questions], "question_ids": [str(x) for x in question_ids]},
        message="Questions extracted from file",
    )


@router.post("/marking-scheme/upload", response_model=SuccessResponse[dict])
async def upload_marking_scheme_file(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(deps.require_teacher),
) -> Any:
    """Upload marking scheme: file → R2 → curriculum parse → extract criteria."""
    client = getattr(request.app.state, "curriculum_http", None)
    if not client:
        raise HTTPException(status_code=503, detail="Curriculum service is not configured (CURRICULUM_SERVICE_URL)")
    content = await file.read()
    key_prefix = f"assessments/{current_user.id}/marking-scheme"
    try:
        file_url = await storage.upload(
            key_prefix,
            file.filename or "marking-scheme.pdf",
            content,
            content_type=file.content_type,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    r_parse = await client.post(
        "/curriculums/parse-document",
        json={"file_url": file_url},
        headers=_curriculum_headers(current_user),
    )
    if r_parse.status_code >= 400:
        raise HTTPException(status_code=r_parse.status_code, detail=_detail_from_response(r_parse))
    markdown = r_parse.json().get("data", {}).get("markdown", "")
    r_extract = await client.post(
        "/curriculums/extract-marking-scheme",
        json={"markdown": markdown},
        headers=_curriculum_headers(current_user),
    )
    if r_extract.status_code >= 400:
        raise HTTPException(status_code=r_extract.status_code, detail=_detail_from_response(r_extract))
    criteria_data = r_extract.json().get("data", {}).get("criteria", [])
    criteria = [MarkingCriterionItem(**c) for c in criteria_data]
    return SuccessResponse(
        data={"criteria": [c.model_dump() for c in criteria]},
        message="Marking scheme extracted from file",
    )


@router.get("/topics", response_model=SuccessResponse[List[dict]])
async def list_topics_from_curriculum(
    request: Request,
    class_id: Optional[UUID] = Query(None, description="Filter topics by class (curriculums linked to this class)"),
    current_user: User = Depends(deps.require_teacher),
) -> Any:
    """Topics from curriculum for 'Select question topics' / 'Detected from [class]'. Optional class_id filter."""
    client = getattr(request.app.state, "curriculum_http", None)
    if not client:
        raise HTTPException(status_code=503, detail="Curriculum service is not configured (CURRICULUM_SERVICE_URL)")
    r = await client.get(
        "/curriculums",
        params={"page": 1, "page_size": 100},
        headers=_curriculum_headers(current_user),
    )
    if r.status_code >= 400:
        detail = r.json().get("detail", r.text) if r.headers.get("content-type", "").startswith("application/json") else r.text
        raise HTTPException(status_code=r.status_code, detail=detail)
    data = r.json().get("data", [])
    topics_out: List[dict] = []
    for curr in data:
        if class_id is not None:
            class_ids = [c.get("id") for c in curr.get("classes", []) if c.get("id")]
            if str(class_id) not in [str(cid) for cid in class_ids]:
                continue
        for t in curr.get("topics", []):
            topics_out.append({
                "id": t.get("id"),
                "title": t.get("title"),
                "curriculum_id": curr.get("id"),
                "curriculum_title": curr.get("title"),
            })
    return SuccessResponse(data=topics_out, message="Topics from curriculum")


@router.get("/analytics/summary", response_model=SuccessResponse[AnalyticsSummary])
async def get_analytics_summary(
    class_id: Optional[UUID] = Query(None, description="Filter by class"),
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """Task Performance Analytics: total assessments, total assignments, average completion rate."""
    summary = await AssessmentService.analytics_summary(db, current_user.id, class_id=class_id)
    return SuccessResponse(data=AnalyticsSummary(**summary))


@router.get("", response_model=PaginatedResponse[AssessmentListRow])
async def list_assessments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    class_id: Optional[UUID] = Query(None, description="Filter by class"),
    type_filter: Optional[str] = Query(None, alias="type", description="oral | written"),
    search: Optional[str] = Query(None, description="Search by title"),
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """List assignments for the teacher (Task Management table)."""
    skip = (page - 1) * page_size
    assignments, total = await AssessmentService.list_assignments(
        db, current_user.id, class_id=class_id, type_filter=type_filter, search=search, skip=skip, limit=page_size
    )
    items = [_assignment_to_list_row(a) for a in assignments]
    total_pages = (total + page_size - 1) // page_size if total else 0
    return PaginatedResponse(
        data=[AssessmentListRow(**x) for x in items],
        meta=PaginationMeta(page=page, page_size=page_size, total=total, total_pages=total_pages),
    )


@router.post("", response_model=SuccessResponse[AssessmentResponse])
async def create_assessment(
    body: AssessmentCreate,
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    Create a new assessment (draft). Teacher console. Optional questions (question_id, points) are linked if provided.

    **IMPORTANT: "Assessment" = "Assignment" (same entity)**
    - This endpoint creates what's stored as an "Assignment" in the database
    - "Assessment" (API) and "Assignment" (Database) are interchangeable terms
    - No separate "/assignments" endpoint exists

    **Differentiation is by the `type` field:**
    - `type: "oral"` → Oral assessments (speaking/listening exercises)
    - `type: "written"` → Written assessments (essays, written tests)

    **JSON Request Example:**
    ```json
    {
      "title": "French Vocabulary Quiz",
      "type": "written",
      "instructions": "Complete all questions carefully",
      "due_date": "2026-03-20T23:59:59Z",
      "class_ids": ["c1fbfe2a-dc95-4627-b355-5abedc2f1184"],
      "enable_ai_marking": true,
      "questions": [
        {
          "question_id": "123e4567-e89b-12d3-a456-426614174000",
          "points": 10
        }
      ]
    }
    ```

    **Required Fields:**
    - `title`: Assessment name (string)
    - `type`: Assessment type - **"oral" or "written"**
    - `class_ids`: Array of class UUIDs (at least one)

    **Optional Fields:**
    - `instructions`: Task instructions for students (string)
    - `due_date`: Due date/time in ISO 8601 format (datetime)
    - `enable_ai_marking`: Enable AI-powered grading (boolean, default: false)
    - `questions`: Array of {question_id, points} from question bank

    **Assessment Types:**
    - **"oral"**: Speaking/listening assessments (audio recordings, presentations, pronunciation)
    - **"written"**: Written assessments (essays, tests, comprehension, grammar exercises)

    **Workflow:**
    1. Create assessment (draft status) - students cannot see it yet
    2. Optionally add/update questions
    3. Publish assessment - makes it visible to students
    4. Monitor submissions
    5. Grade submissions (manual or AI)
    """
    try:
        assignment = await AssessmentService.create_assignment(db, current_user.id, body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return SuccessResponse(
        data=AssessmentResponse.model_validate(assignment),
        message="Assessment created successfully",
    )


@router.get("/{assignment_id}", response_model=SuccessResponse[AssessmentResponse])
async def get_assessment(
    assignment_id: UUID,
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """Get one assessment. Teacher console."""
    assignment = await AssessmentService.get_assignment(db, assignment_id, current_user.id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return SuccessResponse(data=AssessmentResponse.model_validate(assignment))


@router.patch("/{assignment_id}", response_model=SuccessResponse[AssessmentResponse])
async def update_assessment(
    assignment_id: UUID,
    body: AssessmentUpdate,
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """Update an assessment (draft). Teacher console."""
    assignment = await AssessmentService.update_assignment(db, assignment_id, current_user.id, body)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return SuccessResponse(data=AssessmentResponse.model_validate(assignment))


@router.post("/{assignment_id}/publish", response_model=SuccessResponse[AssessmentResponse])
async def publish_assessment(
    assignment_id: UUID,
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """Publish an assessment (set status to published). Teacher console."""
    assignment = await AssessmentService.publish_assignment(db, assignment_id, current_user.id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return SuccessResponse(data=AssessmentResponse.model_validate(assignment), message="Assessment published")


# --- Questions (assignment) ---

@router.get("/{assignment_id}/questions", response_model=SuccessResponse[List[dict]])
async def get_assignment_questions(
    assignment_id: UUID,
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """List questions attached to this assignment (Review generated questions)."""
    rows = await AssessmentService.get_questions_for_assignment(db, assignment_id, current_user.id)
    items = [
        {"question": QuestionResponse.model_validate(q), "points": pts}
        for q, pts in rows
    ]
    return SuccessResponse(data=items)


@router.put("/{assignment_id}/questions", response_model=SuccessResponse)
async def set_assignment_questions(
    assignment_id: UUID,
    body: List[AssignmentQuestionItem],
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """Set questions on an assignment (with points). Teacher console."""
    ok = await AssessmentService.set_assignment_questions(db, assignment_id, current_user.id, body)
    if not ok:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return SuccessResponse(data={"updated": True}, message="Questions updated")


# --- Submissions (Class students list) ---

@router.get("/{assignment_id}/submissions", response_model=PaginatedResponse[SubmissionRow])
async def list_submissions(
    assignment_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="submitted | graded"),
    search: Optional[str] = Query(None, description="Search by student name"),
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """List submissions for an assignment (Students Performance table)."""
    assignment = await AssessmentService.get_assignment(db, assignment_id, current_user.id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    skip = (page - 1) * page_size
    rows, total = await AssessmentService.list_submissions(
        db, assignment_id, current_user.id, status_filter=status, search=search, skip=skip, limit=page_size
    )
    items = []
    for sub, student_name in rows:
        score_pct = (
            float(sub.grade_score or sub.ai_score or 0)
            if (sub.grade_score is not None or sub.ai_score is not None)
            else None
        )
        items.append(
            SubmissionRow(
                id=sub.id,
                student_id=sub.student_id,
                student_name=student_name,
                status=sub.status.value,
                score_percent=score_pct,
                submitted_at=sub.submitted_at,
            )
        )
    total_pages = (total + page_size - 1) // page_size if total else 0
    return PaginatedResponse(
        data=items,
        meta=PaginationMeta(page=page, page_size=page_size, total=total, total_pages=total_pages),
    )


@router.get("/{assignment_id}/submissions/{submission_id}", response_model=SuccessResponse[dict])
async def get_submission(
    assignment_id: UUID,
    submission_id: UUID,
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """Get one submission (View Analytics). Teacher console."""
    sub = await AssessmentService.get_submission(db, assignment_id, submission_id, current_user.id)
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    return SuccessResponse(
        data={
            "id": str(sub.id),
            "student_id": str(sub.student_id),
            "assignment_id": str(sub.assignment_id),
            "status": sub.status.value,
            "submitted_at": sub.submitted_at.isoformat() if sub.submitted_at else None,
            "ai_score": float(sub.ai_score) if sub.ai_score is not None else None,
            "teacher_score": float(sub.teacher_score) if sub.teacher_score is not None else None,
            "grade_score": float(sub.grade_score) if sub.grade_score is not None else None,
        }
    )


@router.patch("/{assignment_id}/submissions/{submission_id}/grade", response_model=SuccessResponse[dict])
async def grade_submission(
    assignment_id: UUID,
    submission_id: UUID,
    body: SubmissionGradeUpdate,
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """Update grade/status for a submission. Teacher console."""
    sub = await AssessmentService.grade_submission(db, assignment_id, submission_id, current_user.id, body)
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    return SuccessResponse(
        data={
            "id": str(sub.id),
            "teacher_score": float(sub.teacher_score) if sub.teacher_score is not None else None,
            "grade_score": float(sub.grade_score) if sub.grade_score is not None else None,
            "status": sub.status.value,
        },
        message="Grade updated",
    )


@router.post(
    "/{assignment_id}/submissions/{submission_id}/grade-with-ai",
    response_model=SuccessResponse[dict],
)
async def grade_submission_with_ai(
    request: Request,
    assignment_id: UUID,
    submission_id: UUID,
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """Mark with AI: score a submission using Bedrock (curriculum service). Requires submission content_url (e.g. PDF)."""
    client = getattr(request.app.state, "curriculum_http", None)
    if not client:
        raise HTTPException(status_code=503, detail="Curriculum service is not configured (CURRICULUM_SERVICE_URL)")
    sub = await AssessmentService.get_submission(db, assignment_id, submission_id, current_user.id)
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    if not sub.content_url:
        raise HTTPException(status_code=400, detail="Submission has no content to grade (content_url required)")
    questions_with_points = await AssessmentService.get_questions_for_assignment(db, assignment_id, current_user.id)
    assignment = await AssessmentService.get_assignment(db, assignment_id, current_user.id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    headers = {"X-School-Id": str(current_user.school_id)}
    if settings.CURRICULUM_INTERNAL_SECRET:
        headers["X-Internal-Secret"] = settings.CURRICULUM_INTERNAL_SECRET

    r_parse = await client.post(
        "/curriculums/parse-document",
        json={"file_url": sub.content_url},
        headers=headers,
    )
    if r_parse.status_code >= 400:
        raise HTTPException(status_code=r_parse.status_code, detail=_detail_from_response(r_parse))
    parsed = r_parse.json()
    submission_markdown = parsed.get("data", {}).get("markdown", "")

    questions_payload = [
        {"question_text": q.question_text, "points": pts, "correct_answer": q.correct_answer or ""}
        for q, pts in questions_with_points
    ]
    r_eval = await client.post(
        "/curriculums/evaluate-submission",
        json={
            "instructions": assignment.instructions or "",
            "questions": questions_payload,
            "submission_markdown": submission_markdown,
            "marking_criteria": None,
        },
        headers=headers,
    )
    if r_eval.status_code >= 400:
        raise HTTPException(status_code=r_eval.status_code, detail=_detail_from_response(r_eval))
    eval_data = r_eval.json().get("data", {})
    score = float(eval_data.get("score", 0))

    await AssessmentService.grade_submission(
        db, assignment_id, submission_id, current_user.id,
        SubmissionGradeUpdate(ai_score=score),
    )
    return SuccessResponse(
        data={"ai_score": score, "feedback": eval_data.get("feedback")},
        message="Submission graded with AI",
    )
