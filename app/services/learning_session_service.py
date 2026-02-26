"""Learning session (room) service for starting/ending and listing sessions."""

from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics import LearningSession
from app.models.enums import SessionStatus, SessionType
from app.utils.time import get_utc_now

from app.services.academic_service import AcademicService


class LearningSessionService:
    @staticmethod
    async def _teacher_teaches_class(db: AsyncSession, teacher_id: UUID, class_id: UUID) -> bool:
        teacher_classes = await AcademicService.get_teacher_classes(db, teacher_id)
        return any(c.id == class_id for c in teacher_classes)

    @staticmethod
    async def list_monitor_cards_for_teacher(
        db: AsyncSession,
        teacher_id: UUID,
    ) -> List[Tuple[UUID, str, int, Optional[LearningSession]]]:
        """
        Return (class_id, class_name, student_count, active_session) for each
        class the teacher teaches. For Figma Room Monitor row of class cards.
        """
        teacher_classes = await AcademicService.get_teacher_classes(db, teacher_id)
        out: List[Tuple[UUID, str, int, Optional[LearningSession]]] = []
        for cls in teacher_classes:
            roster = await AcademicService.get_class_roster(db, cls.id)
            active = await LearningSessionService.get_active_session(db, cls.id)
            out.append((cls.id, cls.name, len(roster), active))
        return out

    @staticmethod
    async def list_sessions_for_class(
        db: AsyncSession,
        class_id: UUID,
        teacher_id: UUID,
        limit: int = 50,
    ) -> List[LearningSession]:
        if not await LearningSessionService._teacher_teaches_class(db, teacher_id, class_id):
            return []
        stmt = (
            select(LearningSession)
            .where(LearningSession.class_id == class_id)
            .order_by(LearningSession.started_at.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_active_session(
        db: AsyncSession,
        class_id: UUID,
    ) -> Optional[LearningSession]:
        stmt = (
            select(LearningSession)
            .where(
                LearningSession.class_id == class_id,
                LearningSession.status == SessionStatus.IN_PROGRESS,
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_session_by_id(
        db: AsyncSession,
        session_id: UUID,
        class_id: Optional[UUID] = None,
    ) -> Optional[LearningSession]:
        stmt = select(LearningSession).where(LearningSession.id == session_id)
        if class_id is not None:
            stmt = stmt.where(LearningSession.class_id == class_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def start_session(
        db: AsyncSession,
        class_id: UUID,
        teacher_id: UUID,
        session_type: SessionType,
    ) -> Optional[LearningSession]:
        if not await LearningSessionService._teacher_teaches_class(db, teacher_id, class_id):
            return None
        active = await LearningSessionService.get_active_session(db, class_id)
        if active:
            return None
        now = get_utc_now()
        session = LearningSession(
            class_id=class_id,
            started_by_user_id=teacher_id,
            session_type=session_type,
            started_at=now,
            status=SessionStatus.IN_PROGRESS,
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return session

    @staticmethod
    async def end_session(
        db: AsyncSession,
        session_id: UUID,
        class_id: UUID,
        teacher_id: UUID,
    ) -> bool:
        if not await LearningSessionService._teacher_teaches_class(db, teacher_id, class_id):
            return False
        session = await LearningSessionService.get_session_by_id(db, session_id, class_id=class_id)
        if not session or session.status != SessionStatus.IN_PROGRESS:
            return False
        session.status = SessionStatus.COMPLETED
        session.ended_at = get_utc_now()
        await db.commit()
        return True
