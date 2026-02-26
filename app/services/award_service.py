"""Award service – Create New Award (Figma: Leaderboard module)."""

from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics import Award
from app.models.user import User
from app.models.enums import UserRole
from app.models.academic import Class, class_enrollments
from app.utils.time import get_utc_now
from app.schemas.award import AwardCreate
from app.services.academic_service import AcademicService


class AwardService:
    """Create and list awards for teacher's classes."""

    @staticmethod
    async def create_awards(
        db: AsyncSession,
        teacher_id: UUID,
        school_id: UUID,
        payload: AwardCreate,
    ) -> Tuple[List[Award], Optional[str]]:
        """
        Create one award per (student_id, class_id). Teacher must teach all classes;
        students must belong to school and be enrolled in at least one of the given classes.
        Returns (list of created Award, error_message if validation failed).
        """
        teacher_classes = await AcademicService.get_teacher_classes(db, teacher_id)
        teacher_class_ids = {c.id for c in teacher_classes}
        for cid in payload.class_ids:
            if cid not in teacher_class_ids:
                return [], "One or more classes are not taught by you"

        # Students must be in school and enrolled in at least one of the classes
        for sid in payload.student_ids:
            user = await db.get(User, sid)
            if not user or user.school_id != school_id or user.role != UserRole.STUDENT or user.deleted_at:
                return [], "One or more students are invalid or not in your school"
            # Check enrollment in at least one of the selected classes
            stmt = select(class_enrollments).where(
                and_(
                    class_enrollments.c.student_id == sid,
                    class_enrollments.c.class_id.in_(payload.class_ids),
                )
            )
            result = await db.execute(stmt)
            if not result.first():
                return [], "Each student must be enrolled in at least one of the selected classes"

        now = get_utc_now()
        created: List[Award] = []
        for sid in payload.student_ids:
            for cid in payload.class_ids:
                # Only create if student is in this class
                stmt = select(class_enrollments).where(
                    and_(
                        class_enrollments.c.student_id == sid,
                        class_enrollments.c.class_id == cid,
                    )
                )
                if (await db.execute(stmt)).first():
                    award = Award(
                        student_id=sid,
                        class_id=cid,
                        title=payload.title,
                        description=payload.criteria,
                        criteria=payload.criteria,
                        awarded_at=now,
                    )
                    db.add(award)
                    created.append(award)
        await db.flush()
        for a in created:
            await db.refresh(a)
        await db.commit()
        return created, None

    @staticmethod
    async def list_teacher_awards(
        db: AsyncSession,
        teacher_id: UUID,
        class_id: Optional[UUID] = None,
        student_id: Optional[UUID] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[dict], int]:
        """List awards for classes the teacher teaches. Optional filter by class_id or student_id."""
        teacher_classes = await AcademicService.get_teacher_classes(db, teacher_id)
        teacher_class_ids = [c.id for c in teacher_classes]
        if not teacher_class_ids:
            return [], 0

        base_filter = Award.class_id.in_(teacher_class_ids)
        if class_id is not None:
            if class_id not in teacher_class_ids:
                return [], 0
            base_filter = and_(base_filter, Award.class_id == class_id)
        if student_id is not None:
            base_filter = and_(base_filter, Award.student_id == student_id)

        total = (await db.execute(select(func.count()).select_from(Award).where(base_filter))).scalar() or 0

        q = (
            select(Award, User.first_name, User.last_name, Class.name, Class.sub_class)
            .join(User, User.id == Award.student_id)
            .join(Class, Class.id == Award.class_id)
            .where(base_filter)
            .order_by(Award.awarded_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await db.execute(q)
        rows = result.all()
        items = [
            {
                "id": r[0].id,
                "student_id": r[0].student_id,
                "class_id": r[0].class_id,
                "title": r[0].title,
                "description": r[0].description,
                "criteria": r[0].criteria,
                "awarded_at": r[0].awarded_at,
                "student_name": f"{r[1] or ''} {r[2] or ''}".strip() or None,
                "class_name": f"{r[3] or ''} - {r[4] or ''}".strip() if r[4] else (r[3] or ""),
            }
            for r in rows
        ]
        return items, total
