"""
Arena management service — teacher console only.
All operations are scoped to the given teacher_id (teacher must teach the arena's class).
"""

from typing import Optional, List, Tuple
from uuid import UUID
import random

from sqlalchemy import select, and_, delete, insert, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.arena import Arena, ArenaCriteria, ArenaRule, arena_moderators
from app.models.academic import Class, teacher_assignments
from app.models.user import User
from app.models.enums import ArenaStatus, UserRole
from app.schemas.communication import ArenaCreate, ArenaUpdate, ArenaSessionConfig


class ArenaService:
    """Teacher-scoped arena CRUD."""

    @staticmethod
    async def _teacher_teaches_class(db: AsyncSession, teacher_id: UUID, class_id: UUID) -> bool:
        result = await db.execute(
            select(teacher_assignments).where(
                teacher_assignments.c.class_id == class_id,
                teacher_assignments.c.teacher_id == teacher_id,
            )
        )
        return result.first() is not None

    @staticmethod
    async def list_arenas(
        db: AsyncSession,
        teacher_id: UUID,
        class_id: Optional[UUID] = None,
        status: Optional[ArenaStatus] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> Tuple[List[Tuple[Arena, Optional[str]]], int]:
        """List arenas for classes the teacher teaches. Returns (Arena, class_name) and total."""
        q = (
            select(Arena, Class.name)
            .join(Class, Class.id == Arena.class_id)
            .join(teacher_assignments, and_(
                teacher_assignments.c.class_id == Class.id,
                teacher_assignments.c.teacher_id == teacher_id,
            ))
        )
        if class_id is not None:
            q = q.where(Arena.class_id == class_id)
        if status is not None:
            q = q.where(Arena.status == status)

        count_q = select(func.count()).select_from(q.subquery())
        total = (await db.execute(count_q)).scalar() or 0

        q = q.offset(skip).limit(limit).order_by(Arena.start_time.desc().nullslast(), Arena.created_at.desc())
        result = await db.execute(q)
        rows = result.all()
        return [(row[0], row[1]) for row in rows], total

    @staticmethod
    async def get_arena(
        db: AsyncSession,
        arena_id: UUID,
        teacher_id: UUID,
    ) -> Optional[Arena]:
        """Get arena by id if the teacher teaches its class."""
        result = await db.execute(
            select(Arena)
            .options(
                selectinload(Arena.criteria),
                selectinload(Arena.rules),
                selectinload(Arena.class_),
            )
            .join(teacher_assignments, and_(
                teacher_assignments.c.class_id == Arena.class_id,
                teacher_assignments.c.teacher_id == teacher_id,
            ))
            .where(Arena.id == arena_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create_arena(
        db: AsyncSession,
        teacher_id: UUID,
        data: ArenaCreate,
    ) -> Optional[Arena]:
        """Create arena for a class the teacher teaches. Adds teacher as moderator."""
        if not await ArenaService._teacher_teaches_class(db, teacher_id, data.class_id):
            return None
        arena = Arena(
            class_id=data.class_id,
            title=data.title,
            description=data.description,
            status=ArenaStatus.DRAFT,
            start_time=data.start_time,
            duration_minutes=data.duration_minutes,
        )
        db.add(arena)
        await db.flush()
        for name, weight in data.criteria.items():
            c = ArenaCriteria(arena_id=arena.id, name=name, weight_percentage=weight)
            db.add(c)
        for desc in data.rules:
            r = ArenaRule(arena_id=arena.id, description=desc)
            db.add(r)
        await db.execute(
            insert(arena_moderators).values(arena_id=arena.id, user_id=teacher_id)
        )
        await db.commit()
        await db.refresh(arena)
        return arena

    @staticmethod
    async def update_arena(  # noqa: C901
        db: AsyncSession,
        arena_id: UUID,
        teacher_id: UUID,
        data: ArenaUpdate,
    ) -> Optional[Arena]:
        """Update arena (teacher must teach its class). Replaces criteria/rules if provided."""
        arena = await ArenaService.get_arena(db, arena_id, teacher_id)
        if not arena:
            return None
        if data.title is not None:
            arena.title = data.title
        if data.description is not None:
            arena.description = data.description
        if data.status is not None:
            arena.status = data.status
        if data.start_time is not None:
            arena.start_time = data.start_time
        if data.duration_minutes is not None:
            arena.duration_minutes = data.duration_minutes
        if data.criteria is not None:
            await db.execute(delete(ArenaCriteria).where(ArenaCriteria.arena_id == arena_id))
            for name, weight in data.criteria.items():
                db.add(ArenaCriteria(arena_id=arena_id, name=name, weight_percentage=weight))
        if data.rules is not None:
            await db.execute(delete(ArenaRule).where(ArenaRule.arena_id == arena_id))
            for desc in data.rules:
                db.add(ArenaRule(arena_id=arena_id, description=desc))
        await db.commit()
        await db.refresh(arena)
        return arena

    # --- Phase 1: Session Configuration ---

    @staticmethod
    async def search_students(
        db: AsyncSession,
        class_id: UUID,
        name: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> Tuple[List[User], int]:
        """Search for students in a class by name."""
        q = (
            select(User)
            .join(User.enrollments)
            .where(
                User.enrollments.any(class_id=class_id),
                User.role == UserRole.STUDENT,
                User.is_active == True
            )
        )

        if name:
            q = q.where(User.name.ilike(f"%{name}%"))

        # Count total
        count_q = select(func.count()).select_from(q.subquery())
        total = (await db.execute(count_q)).scalar() or 0

        # Get paginated results
        q = q.offset(skip).limit(limit).order_by(User.name)
        result = await db.execute(q)
        students = list(result.scalars().all())

        return students, total

    @staticmethod
    async def initialize_arena_session(
        db: AsyncSession,
        arena_id: UUID,
        teacher_id: UUID,
        config: ArenaSessionConfig,
    ) -> Optional[Arena]:
        """Initialize arena session with configuration and selected participants."""
        # Verify teacher has access
        arena = await ArenaService.get_arena(db, arena_id, teacher_id)
        if not arena:
            return None

        # Update arena with session configuration
        arena.arena_mode = config.arena_mode
        arena.judging_mode = config.judging_mode
        arena.ai_co_judge_enabled = config.ai_co_judge_enabled
        arena.student_selection_mode = config.student_selection_mode
        arena.session_state = "initialized"

        if config.team_size:
            arena.team_size = config.team_size

        # TODO Phase 4: Create arena_participants entries for selected students
        # For now, just update the arena configuration

        await db.commit()
        await db.refresh(arena)
        return arena

    @staticmethod
    async def randomize_student_selection(
        db: AsyncSession,
        class_id: UUID,
        participant_count: int,
    ) -> List[User]:
        """Randomly select N students from a class."""
        # Get all active students in class
        q = (
            select(User)
            .join(User.enrollments)
            .where(
                User.enrollments.any(class_id=class_id),
                User.role == UserRole.STUDENT,
                User.is_active == True
            )
        )
        result = await db.execute(q)
        all_students = list(result.scalars().all())

        # Randomly select
        if len(all_students) <= participant_count:
            return all_students

        return random.sample(all_students, participant_count)

    @staticmethod
    async def hybrid_student_selection(
        db: AsyncSession,
        class_id: UUID,
        manual_selections: List[UUID],
        randomize_count: int,
    ) -> List[User]:
        """Combine manual selections with random selections."""
        # Get manually selected students
        if manual_selections:
            q = select(User).where(User.id.in_(manual_selections))
            result = await db.execute(q)
            selected_students = list(result.scalars().all())
        else:
            selected_students = []

        # Get remaining students (excluding manual selections)
        q = (
            select(User)
            .join(User.enrollments)
            .where(
                User.enrollments.any(class_id=class_id),
                User.role == UserRole.STUDENT,
                User.is_active == True
            )
        )

        if manual_selections:
            q = q.where(User.id.not_in(manual_selections))

        result = await db.execute(q)
        remaining_students = list(result.scalars().all())

        # Randomly select from remaining
        if randomize_count > 0 and remaining_students:
            random_count = min(randomize_count, len(remaining_students))
            random_selections = random.sample(remaining_students, random_count)
            selected_students.extend(random_selections)

        return selected_students
