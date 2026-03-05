"""Curriculum business logic (CRUD + AI extraction/merge)."""

import os
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, func, delete, insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import settings
from models.curriculum import Curriculum, Topic, curriculum_classes
from models.refs import Language
from models.enums import CurriculumStatus, CurriculumSourceType
from schemas.content import (
    CurriculumCreate,
    CurriculumUpdate,
    TopicCreate,
    TopicUpdate,
    TopicProposal,
    ExtractedQuestion,
    MarkingCriterion,
    EvaluateSubmissionResponse,
)


def _get_ai_client():
    from utils.ai import get_ai_client
    return get_ai_client()


class CurriculumService:
    @staticmethod
    async def get_curriculums(
        db: AsyncSession,
        school_id: UUID,
        skip: int = 0,
        limit: int = 100,
        status: Optional[CurriculumStatus] = None,
        language_id: Optional[int] = None,
        search: Optional[str] = None,
    ) -> tuple[List[Curriculum], int]:
        query = (
            select(Curriculum)
            .where(Curriculum.school_id == school_id)
            .options(
                selectinload(Curriculum.classes),
                selectinload(Curriculum.language),
                # Don't load topics in list view for performance
            )
        )
        if status:
            query = query.where(Curriculum.status == status)
        if language_id:
            query = query.where(Curriculum.language_id == language_id)
        if search:
            query = query.where(Curriculum.title.ilike(f"%{search}%"))

        # Optimize: Build count query from base conditions without subquery
        count_query = select(func.count()).select_from(Curriculum).where(Curriculum.school_id == school_id)
        if status:
            count_query = count_query.where(Curriculum.status == status)
        if language_id:
            count_query = count_query.where(Curriculum.language_id == language_id)
        if search:
            count_query = count_query.where(Curriculum.title.ilike(f"%{search}%"))

        total = (await db.execute(count_query)).scalar_one()
        result = await db.execute(
            query.offset(skip).limit(limit).order_by(Curriculum.created_at.desc())
        )
        return list(result.scalars().all()), total

    @staticmethod
    async def get_curriculum_by_id(
        db: AsyncSession, curriculum_id: UUID, school_id: UUID
    ) -> Optional[Curriculum]:
        result = await db.execute(
            select(Curriculum)
            .where(Curriculum.id == curriculum_id, Curriculum.school_id == school_id)
            .options(
                selectinload(Curriculum.classes),
                selectinload(Curriculum.language),
                selectinload(Curriculum.topics),
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create_curriculum(
        db: AsyncSession,
        school_id: UUID,
        curriculum_in: CurriculumCreate,
    ) -> Curriculum:
        file_url = getattr(curriculum_in, "file_url", None) or None
        new_curriculum = Curriculum(
            school_id=school_id,
            title=curriculum_in.title,
            description=curriculum_in.description,
            language_id=curriculum_in.language_id,
            source_type=curriculum_in.source_type,
            file_url=file_url,
            status=CurriculumStatus.PUBLISHED,
        )
        db.add(new_curriculum)
        await db.flush()

        if curriculum_in.class_ids:
            for class_id in curriculum_in.class_ids:
                await db.execute(
                    insert(curriculum_classes).values(
                        curriculum_id=new_curriculum.id,
                        class_id=class_id,
                    )
                )

        await db.commit()
        await db.refresh(new_curriculum)
        return await CurriculumService.get_curriculum_by_id(
            db, new_curriculum.id, school_id
        )

    @staticmethod
    async def update_curriculum(
        db: AsyncSession,
        curriculum_id: UUID,
        school_id: UUID,
        curriculum_update: CurriculumUpdate,
    ) -> Optional[Curriculum]:
        curriculum = await CurriculumService.get_curriculum_by_id(
            db, curriculum_id, school_id
        )
        if not curriculum:
            return None

        update_data = curriculum_update.model_dump(exclude_unset=True)
        class_ids = update_data.pop("class_ids", None)

        for field, value in update_data.items():
            setattr(curriculum, field, value)

        if class_ids is not None:
            await db.execute(
                delete(curriculum_classes).where(
                    curriculum_classes.c.curriculum_id == curriculum_id
                )
            )
            for cid in class_ids:
                await db.execute(
                    insert(curriculum_classes).values(
                        curriculum_id=curriculum_id, class_id=cid
                    )
                )

        await db.commit()
        await db.refresh(curriculum)
        return curriculum

    @staticmethod
    async def delete_curriculum(
        db: AsyncSession, curriculum_id: UUID, school_id: UUID
    ) -> bool:
        curriculum = await CurriculumService.get_curriculum_by_id(
            db, curriculum_id, school_id
        )
        if not curriculum:
            return False
        await db.delete(curriculum)
        await db.commit()
        return True

    @staticmethod
    async def extract_topics(
        db: AsyncSession, curriculum_id: UUID, file_url_or_path: str
    ) -> List[Topic]:
        from utils.document_parser import parse_document_to_markdown

        markdown_content = await parse_document_to_markdown(file_url_or_path)

        ai_client = _get_ai_client()
        topics_data = await ai_client.chat.completions.create(
            model=settings.BEDROCK_MODEL_ID,
            response_model=List[TopicCreate],
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a specialized curriculum analyst. Extract a structured list of topics "
                        "from the syllabus text provided. Maintain the original order. For each topic include: "
                        "title, content (brief 2-4 sentence summary when available), and specific learning objectives."
                    ),
                },
                {"role": "user", "content": f"Syllabus Content:\n\n{markdown_content}"},
            ],
        )

        topics_to_insert = []
        for index, item in enumerate(topics_data, 1):
            db_topic = Topic(
                curriculum_id=curriculum_id,
                title=item.title,
                duration_hours=item.duration_hours,
                learning_objectives=item.learning_objectives,
                content=item.content,
                order_index=item.order_index or index,
            )
            db.add(db_topic)
            topics_to_insert.append(db_topic)

        await db.commit()
        for t in topics_to_insert:
            await db.refresh(t)
        return topics_to_insert

    @staticmethod
    async def generate_curriculum_topics(
        db: AsyncSession, prompt: str, language_id: int
    ) -> List[TopicCreate]:
        result = await db.execute(select(Language).where(Language.id == language_id))
        lang = result.scalar_one_or_none()
        lang_name = lang.name if lang else "English"

        if os.getenv("TEST_MODE") == "true":
            return [TopicCreate(title="Test Topic", duration_hours=1.0)]

        ai_client = _get_ai_client()
        topics = await ai_client.chat.completions.create(
            model=settings.BEDROCK_MODEL_ID,
            response_model=List[TopicCreate],
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"You are an expert curriculum designer for {lang_name} language learning. "
                        "Output 3–6 topics only. Keep each topic's content to one sentence; 2–3 learning objectives per topic."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Generate a curriculum structure for: {prompt}. "
                        "For each topic provide: title, one-sentence content summary, 2–3 learning objectives, and duration_hours (e.g. 0.5–2). "
                        "Return a JSON array only."
                    ),
                },
            ],
        )
        return topics

    @staticmethod
    async def update_topic(
        db: AsyncSession, topic_id: UUID, update_data: TopicUpdate
    ) -> Optional[Topic]:
        result = await db.execute(select(Topic).where(Topic.id == topic_id))
        topic = result.scalar_one_or_none()
        if not topic:
            return None
        update_dict = update_data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(topic, key, value)
        await db.commit()
        await db.refresh(topic)
        return topic

    @staticmethod
    async def propose_merge_strategy(
        db: AsyncSession,
        teacher_curriculum: Curriculum,
        library_curriculum: Curriculum,
    ) -> List[TopicProposal]:
        teacher_context = [
            {
                "title": t.title,
                "duration": t.duration_hours,
                "objectives": t.learning_objectives,
            }
            for t in teacher_curriculum.topics
        ]
        library_context = [
            {
                "title": t.title,
                "duration": t.duration_hours,
                "objectives": t.learning_objectives,
            }
            for t in library_curriculum.topics
        ]

        ai_client = _get_ai_client()
        proposals = await ai_client.chat.completions.create(
            model=settings.BEDROCK_MODEL_ID,
            response_model=List[TopicProposal],
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a curriculum synchronization expert. Your goal is to merge a Teacher's "
                        "curriculum with a Master Library curriculum. Identify overlaps and redundant topics. "
                        "Propose actions for each topic: 'blend' (combine both), 'replace' (use Library version), "
                        "'add' (keep unique topic), or 'keep' (no change needed). "
                        "Return a unified sequence of TopicProposal objects."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Teacher topics: {teacher_context}\n\nLibrary sessions: {library_context}",
                },
            ],
        )
        return proposals

    @staticmethod
    async def confirm_merge(
        db: AsyncSession,
        school_id: UUID,
        base_curriculum_id: UUID,
        final_topics: List[TopicCreate],
    ) -> Curriculum:
        from fastapi import HTTPException

        base_curr = await CurriculumService.get_curriculum_by_id(
            db, base_curriculum_id, school_id
        )
        if not base_curr:
            raise HTTPException(status_code=404, detail="Base curriculum not found")

        merged_curriculum = Curriculum(
            school_id=school_id,
            title=f"{base_curr.title} (Integrated Edition)",
            language_id=base_curr.language_id,
            source_type=CurriculumSourceType.MERGED,
            status=CurriculumStatus.DRAFT,
        )
        db.add(merged_curriculum)
        await db.flush()

        for index, item in enumerate(final_topics, 1):
            db_topic = Topic(
                curriculum_id=merged_curriculum.id,
                title=item.title,
                duration_hours=item.duration_hours,
                learning_objectives=item.learning_objectives,
                content=item.content,
                order_index=item.order_index or index,
            )
            db.add(db_topic)

        await db.commit()
        await db.refresh(merged_curriculum)
        return await CurriculumService.get_curriculum_by_id(
            db, merged_curriculum.id, school_id
        )

    @staticmethod
    async def generate_assessment_questions(
        topics: List[str],
        assignment_type: str = "written",
    ) -> List[ExtractedQuestion]:
        """Generate assessment questions from topics using Bedrock (Generate with AI)."""
        if os.getenv("TEST_MODE") == "true":
            return [
                ExtractedQuestion(
                    question_text="Sample question from topic",
                    type="open_text",
                    correct_answer=None,
                )
            ]
        ai_client = _get_ai_client()
        type_hint = "oral (speaking/listening)" if assignment_type == "oral" else "written"
        prompt = (
            f"Generate 5–10 assessment questions for a {type_hint} language assessment. "
            "Topics to cover: " + ", ".join(topics) + ". "
            "For each question include: question_text, type (one of: multiple_choice, open_text, oral), "
            "correct_answer when applicable, and options for multiple_choice."
        )
        questions = await ai_client.chat.completions.create(
            model=settings.BEDROCK_MODEL_ID,
            response_model=List[ExtractedQuestion],
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert language assessment designer. Output a structured list of questions "
                        "suitable for the given topics and assessment type. Use clear question_text and appropriate "
                        "type (multiple_choice, open_text, oral)."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
        return questions

    @staticmethod
    async def extract_questions_from_markdown(markdown: str) -> List[ExtractedQuestion]:
        """Extract structured questions from document markdown (Upload questions manually)."""
        if os.getenv("TEST_MODE") == "true":
            return [
                ExtractedQuestion(question_text="Sample extracted question", type="open_text", correct_answer=None),
            ]
        ai_client = _get_ai_client()
        questions = await ai_client.chat.completions.create(
            model=settings.BEDROCK_MODEL_ID,
            response_model=List[ExtractedQuestion],
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an assessment designer. Extract a structured list of questions from the document. "
                        "For each question include: question_text, type (multiple_choice, open_text, or oral), "
                        "correct_answer when evident, and options for multiple_choice."
                    ),
                },
                {"role": "user", "content": f"Document content (markdown):\n\n{markdown}"},
            ],
        )
        return questions

    @staticmethod
    async def extract_marking_scheme_from_markdown(markdown: str) -> List[MarkingCriterion]:
        """Extract marking criteria from document markdown (Upload marking scheme)."""
        if os.getenv("TEST_MODE") == "true":
            return [
                MarkingCriterion(criterion="Sample criterion", max_points=10, description="Test"),
            ]
        ai_client = _get_ai_client()
        criteria = await ai_client.chat.completions.create(
            model=settings.BEDROCK_MODEL_ID,
            response_model=List[MarkingCriterion],
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an assessment designer. Extract marking criteria from the document. "
                        "For each criterion include: criterion (short name), max_points (integer), description (optional)."
                    ),
                },
                {"role": "user", "content": f"Document content (markdown):\n\n{markdown}"},
            ],
        )
        return criteria

    @staticmethod
    async def evaluate_submission(
        instructions: Optional[str],
        questions: List[dict],
        submission_markdown: str,
        marking_criteria: Optional[List[dict]] = None,
    ) -> EvaluateSubmissionResponse:
        """Score a submission using Bedrock (Mark with AI). Returns score 0–100 and optional feedback."""
        if os.getenv("TEST_MODE") == "true":
            return EvaluateSubmissionResponse(score=75.0, feedback="Sample AI feedback (test mode).")
        ai_client = _get_ai_client()

        questions_desc = "\n".join(
            f"- Q: {q.get('question_text', '')} (points: {q.get('points', 1)}; model answer: {q.get('correct_answer', 'N/A')})"
            for q in questions
        )
        criteria_desc = ""
        if marking_criteria:
            criteria_desc = "\nMarking criteria:\n" + "\n".join(
                f"- {c.get('criterion', '')}: max {c.get('max_points', 0)}"
                for c in marking_criteria
            )

        prompt = (
            f"Assignment instructions:\n{instructions or 'None'}\n\n"
            f"Questions and model answers:\n{questions_desc}\n{criteria_desc}\n\n"
            f"Student submission (markdown):\n{submission_markdown}\n\n"
            "Score the submission from 0 to 100 and provide brief feedback."
        )

        result = await ai_client.chat.completions.create(
            model=settings.BEDROCK_MODEL_ID,
            response_model=EvaluateSubmissionResponse,
            messages=[
                {
                    "role": "system",
                    "content": "You are an assessment grader. Output a JSON object with 'score' (0–100) and 'feedback' (brief text).",
                },
                {"role": "user", "content": prompt},
            ],
        )
        return result
