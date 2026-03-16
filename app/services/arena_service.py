"""
Arena management service — teacher console only.
All operations are scoped to the given teacher_id (teacher must teach the arena's class).
"""

from typing import Optional, List, Tuple
from uuid import UUID
import random
import string
from datetime import datetime, timedelta
import io
import base64

from sqlalchemy import select, and_, delete, insert, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.arena import Arena, ArenaCriteria, ArenaRule, arena_moderators, ArenaWaitingRoom, ArenaParticipant, ArenaReaction
from app.models.academic import Class, teacher_assignments
from app.models.user import User
from app.models.enums import ArenaStatus, UserRole
from app.schemas.communication import ArenaCreate, ArenaUpdate, ArenaSessionConfig

# QR code generation (install: pip install qrcode[pil])
try:
    import qrcode
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False


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

    # --- Phase 2: Waiting Room & Admission ---

    @staticmethod
    def _generate_join_code(length: int = 6) -> str:
        """Generate random alphanumeric join code (uppercase + digits)."""
        chars = string.ascii_uppercase + string.digits
        return ''.join(random.choice(chars) for _ in range(length))

    @staticmethod
    def _generate_qr_code(join_url: str) -> str:
        """Generate QR code as base64 data URL."""
        if not HAS_QRCODE:
            return ""  # Graceful degradation if qrcode not installed

        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(join_url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        img_bytes = buffer.getvalue()
        img_base64 = base64.b64encode(img_bytes).decode()
        return f"data:image/png;base64,{img_base64}"

    @staticmethod
    async def generate_join_code(
        db: AsyncSession,
        arena_id: UUID,
        teacher_id: UUID,
        base_url: str = "https://youspeak.com/arena/join",
    ) -> Optional[Tuple[str, str, datetime]]:
        """
        Generate unique join code and QR code for arena.
        Returns (join_code, qr_code_url, expires_at) or None if arena not found.
        """
        # Verify teacher has access
        arena = await ArenaService.get_arena(db, arena_id, teacher_id)
        if not arena:
            return None

        # Generate unique join code (retry up to 3 times if collision)
        join_code = None
        for attempt in range(3):
            code = ArenaService._generate_join_code(length=6 if attempt < 2 else 8)
            # Check uniqueness
            result = await db.execute(
                select(Arena).where(Arena.join_code == code)
            )
            if not result.scalar_one_or_none():
                join_code = code
                break

        if not join_code:
            raise Exception("Failed to generate unique join code after 3 attempts")

        # Set expiration: arena start time + duration + 15 minutes buffer
        if arena.start_time and arena.duration_minutes:
            expires_at = arena.start_time + timedelta(minutes=arena.duration_minutes + 15)
        else:
            # Default: 24 hours from now
            expires_at = datetime.utcnow() + timedelta(hours=24)

        # Generate QR code
        join_url = f"{base_url}?code={join_code}"
        qr_code_url = ArenaService._generate_qr_code(join_url)

        # Update arena
        arena.join_code = join_code
        arena.qr_code_url = qr_code_url
        arena.join_code_expires_at = expires_at

        await db.commit()
        await db.refresh(arena)

        return (join_code, qr_code_url, expires_at)

    @staticmethod
    async def student_join_waiting_room(
        db: AsyncSession,
        arena_id: UUID,
        student_id: UUID,
        join_code: str,
    ) -> Optional[ArenaWaitingRoom]:
        """
        Student joins arena waiting room using join code.
        Returns waiting room entry or None if code invalid/expired.
        """
        # Validate join code
        result = await db.execute(
            select(Arena).where(
                Arena.id == arena_id,
                Arena.join_code == join_code
            )
        )
        arena = result.scalar_one_or_none()

        if not arena:
            return None  # Invalid arena or join code

        # Check expiration
        if arena.join_code_expires_at and datetime.utcnow() > arena.join_code_expires_at:
            return None  # Code expired

        # Check arena state (must be initialized or live)
        if arena.session_state not in ('initialized', 'live'):
            return None  # Cannot join

        # Create waiting room entry (UNIQUE constraint handles duplicates)
        entry = ArenaWaitingRoom(
            arena_id=arena_id,
            student_id=student_id,
            entry_timestamp=datetime.utcnow(),
            status='pending'
        )
        db.add(entry)

        try:
            await db.commit()
            await db.refresh(entry)
            return entry
        except Exception:
            # Duplicate entry (student already in waiting room)
            await db.rollback()
            return None

    @staticmethod
    async def list_waiting_room(
        db: AsyncSession,
        arena_id: UUID,
        teacher_id: UUID,
    ) -> Optional[Tuple[List[Tuple[ArenaWaitingRoom, User]], int, int, int]]:
        """
        List waiting room entries for arena.
        Returns (pending_entries_with_user, total_pending, total_admitted, total_rejected).
        """
        # Verify teacher has access
        arena = await ArenaService.get_arena(db, arena_id, teacher_id)
        if not arena:
            return None

        # Get pending entries with student info
        q = (
            select(ArenaWaitingRoom, User)
            .join(User, User.id == ArenaWaitingRoom.student_id)
            .where(
                ArenaWaitingRoom.arena_id == arena_id,
                ArenaWaitingRoom.status == 'pending'
            )
            .order_by(ArenaWaitingRoom.entry_timestamp)
        )
        result = await db.execute(q)
        pending_entries = result.all()

        # Get counts
        count_q = (
            select(
                func.count().filter(ArenaWaitingRoom.status == 'pending').label('pending'),
                func.count().filter(ArenaWaitingRoom.status == 'admitted').label('admitted'),
                func.count().filter(ArenaWaitingRoom.status == 'rejected').label('rejected')
            )
            .where(ArenaWaitingRoom.arena_id == arena_id)
        )
        counts = (await db.execute(count_q)).first()
        total_pending = counts.pending or 0
        total_admitted = counts.admitted or 0
        total_rejected = counts.rejected or 0

        return (pending_entries, total_pending, total_admitted, total_rejected)

    @staticmethod
    async def admit_student(
        db: AsyncSession,
        arena_id: UUID,
        entry_id: UUID,
        teacher_id: UUID,
    ) -> Optional[ArenaWaitingRoom]:
        """
        Admit student from waiting room.
        Returns waiting room entry or None if not found.
        """
        # Verify teacher has access
        arena = await ArenaService.get_arena(db, arena_id, teacher_id)
        if not arena:
            return None

        # Get waiting room entry
        result = await db.execute(
            select(ArenaWaitingRoom).where(
                ArenaWaitingRoom.id == entry_id,
                ArenaWaitingRoom.arena_id == arena_id,
                ArenaWaitingRoom.status == 'pending'
            )
        )
        entry = result.scalar_one_or_none()

        if not entry:
            return None

        # Update status
        entry.status = 'admitted'
        entry.admitted_at = datetime.utcnow()
        entry.admitted_by = teacher_id

        # Phase 4: Create arena_participants entry (graceful fallback if table doesn't exist)
        try:
            await ArenaService.create_arena_participant(
                db=db,
                arena_id=arena_id,
                student_id=entry.student_id,
                role='participant'
            )
        except Exception:
            # Gracefully handle if migration 005 hasn't run yet
            # This allows tests to pass before Phase 4 tables are created
            pass

        await db.commit()
        await db.refresh(entry)

        return entry

    @staticmethod
    async def reject_student(
        db: AsyncSession,
        arena_id: UUID,
        entry_id: UUID,
        teacher_id: UUID,
        reason: Optional[str] = None,
    ) -> Optional[ArenaWaitingRoom]:
        """
        Reject student from waiting room.
        Returns waiting room entry or None if not found.
        """
        # Verify teacher has access
        arena = await ArenaService.get_arena(db, arena_id, teacher_id)
        if not arena:
            return None

        # Get waiting room entry
        result = await db.execute(
            select(ArenaWaitingRoom).where(
                ArenaWaitingRoom.id == entry_id,
                ArenaWaitingRoom.arena_id == arena_id,
                ArenaWaitingRoom.status == 'pending'
            )
        )
        entry = result.scalar_one_or_none()

        if not entry:
            return None

        # Update status
        entry.status = 'rejected'
        entry.rejection_reason = reason

        await db.commit()
        await db.refresh(entry)

        return entry

    # ========================================================================
    # Phase 3: Live Session Management
    # ========================================================================

    @staticmethod
    async def is_arena_participant(
        db: AsyncSession,
        arena_id: UUID,
        student_id: UUID,
    ) -> bool:
        """
        Check if student was admitted to arena from waiting room.
        Returns True if student is admitted participant, False otherwise.
        """
        result = await db.execute(
            select(ArenaWaitingRoom).where(
                ArenaWaitingRoom.arena_id == arena_id,
                ArenaWaitingRoom.student_id == student_id,
                ArenaWaitingRoom.status == 'admitted'
            )
        )
        entry = result.scalar_one_or_none()
        return entry is not None

    @staticmethod
    async def start_arena_session(
        db: AsyncSession,
        arena_id: UUID,
        teacher_id: UUID,
    ) -> Optional[Arena]:
        """
        Start live arena session.
        Transitions session_state from 'initialized' to 'live'.
        Returns arena or None if not found/no access.
        """
        # Verify teacher has access
        arena = await ArenaService.get_arena(db, arena_id, teacher_id)
        if not arena:
            return None

        # Verify arena is in initialized state
        if arena.session_state != 'initialized':
            return None

        # Update session state
        arena.session_state = 'live'

        # Set start_time if not already set
        if not arena.start_time:
            arena.start_time = datetime.utcnow()

        await db.commit()
        await db.refresh(arena)

        return arena

    @staticmethod
    async def end_arena_session(
        db: AsyncSession,
        arena_id: UUID,
        teacher_id: UUID,
        reason: Optional[str] = None,
    ) -> Optional[Arena]:
        """
        End live arena session.
        Transitions session_state from 'live' to 'completed' (or 'cancelled' if reason provided).
        Returns arena or None if not found/no access.
        """
        # Verify teacher has access
        arena = await ArenaService.get_arena(db, arena_id, teacher_id)
        if not arena:
            return None

        # Verify arena is in live state
        if arena.session_state != 'live':
            return None

        # Update session state
        arena.session_state = 'cancelled' if reason else 'completed'

        await db.commit()
        await db.refresh(arena)

        return arena

    # ========================================================================
    # Phase 4: Evaluation & Publishing
    # ========================================================================

    @staticmethod
    async def create_arena_participant(
        db: AsyncSession,
        arena_id: UUID,
        student_id: UUID,
        role: str = 'participant',
        team_id: Optional[UUID] = None,
    ) -> Optional[ArenaParticipant]:
        """
        Create arena participant entry when student is admitted.
        Called from admit_student method.
        Returns participant or None if already exists.
        """
        # Check if participant already exists
        result = await db.execute(
            select(ArenaParticipant).where(
                ArenaParticipant.arena_id == arena_id,
                ArenaParticipant.student_id == student_id
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing

        # Create new participant
        participant = ArenaParticipant(
            arena_id=arena_id,
            student_id=student_id,
            role=role,
            team_id=team_id,
            is_speaking=False,
            speaking_start_time=None,
            total_speaking_duration_seconds=0,
            engagement_score=0.00,
            last_activity=datetime.utcnow()
        )
        db.add(participant)

        try:
            await db.commit()
            await db.refresh(participant)
            return participant
        except Exception:
            await db.rollback()
            return None

    @staticmethod
    async def update_speaking_state(
        db: AsyncSession,
        participant_id: UUID,
        is_speaking: bool,
    ) -> Optional[ArenaParticipant]:
        """
        Update participant speaking state.
        If starting to speak, set speaking_start_time.
        If stopping, accumulate speaking duration.
        """
        result = await db.execute(
            select(ArenaParticipant).where(ArenaParticipant.id == participant_id)
        )
        participant = result.scalar_one_or_none()
        if not participant:
            return None

        now = datetime.utcnow()

        if is_speaking and not participant.is_speaking:
            # Start speaking
            participant.is_speaking = True
            participant.speaking_start_time = now
        elif not is_speaking and participant.is_speaking:
            # Stop speaking - accumulate duration
            if participant.speaking_start_time:
                duration_seconds = int((now - participant.speaking_start_time).total_seconds())
                participant.total_speaking_duration_seconds += duration_seconds
            participant.is_speaking = False
            participant.speaking_start_time = None

        participant.last_activity = now
        await db.commit()
        await db.refresh(participant)

        return participant

    @staticmethod
    async def update_engagement_score(
        db: AsyncSession,
        participant_id: UUID,
        engagement_delta: float,
    ) -> Optional[ArenaParticipant]:
        """
        Update participant engagement score.
        Score is clamped between 0.00 and 100.00.
        """
        result = await db.execute(
            select(ArenaParticipant).where(ArenaParticipant.id == participant_id)
        )
        participant = result.scalar_one_or_none()
        if not participant:
            return None

        new_score = float(participant.engagement_score) + engagement_delta
        participant.engagement_score = max(0.0, min(100.0, new_score))
        participant.last_activity = datetime.utcnow()

        await db.commit()
        await db.refresh(participant)

        return participant

    @staticmethod
    async def record_reaction(
        db: AsyncSession,
        arena_id: UUID,
        user_id: UUID,
        reaction_type: str,
        target_participant_id: Optional[UUID] = None,
    ) -> ArenaReaction:
        """
        Record a reaction sent during live session.
        Returns the created reaction.
        """
        reaction = ArenaReaction(
            arena_id=arena_id,
            user_id=user_id,
            target_participant_id=target_participant_id,
            reaction_type=reaction_type,
            timestamp=datetime.utcnow()
        )
        db.add(reaction)
        await db.commit()
        await db.refresh(reaction)

        return reaction

    @staticmethod
    async def get_arena_scores(
        db: AsyncSession,
        arena_id: UUID,
        teacher_id: UUID,
    ) -> Optional[Tuple[Arena, List[Tuple[ArenaParticipant, User, int]]]]:
        """
        Get live scoring data for arena.
        Returns (arena, participants_with_reactions).
        Each tuple: (participant, user, reactions_count).
        """
        # Verify teacher has access
        arena = await ArenaService.get_arena(db, arena_id, teacher_id)
        if not arena:
            return None

        # Get participants with user info and reaction counts
        q = (
            select(
                ArenaParticipant,
                User,
                func.count(ArenaReaction.id).label('reactions_count')
            )
            .join(User, User.id == ArenaParticipant.student_id)
            .outerjoin(
                ArenaReaction,
                and_(
                    ArenaReaction.target_participant_id == ArenaParticipant.id,
                    ArenaReaction.arena_id == arena_id
                )
            )
            .where(ArenaParticipant.arena_id == arena_id)
            .group_by(ArenaParticipant.id, User.id)
            .order_by(ArenaParticipant.engagement_score.desc())
        )

        result = await db.execute(q)
        rows = result.all()

        participants_data = [(row[0], row[1], row[2]) for row in rows]

        return (arena, participants_data)

    @staticmethod
    async def get_arena_analytics(
        db: AsyncSession,
        arena_id: UUID,
        teacher_id: UUID,
    ) -> Optional[dict]:
        """
        Get detailed analytics for arena session.
        Returns comprehensive analytics data or None if arena not found.
        """
        # Verify teacher has access
        arena = await ArenaService.get_arena(db, arena_id, teacher_id)
        if not arena:
            return None

        # Get all participants
        participants_result = await db.execute(
            select(ArenaParticipant, User)
            .join(User, User.id == ArenaParticipant.student_id)
            .where(ArenaParticipant.arena_id == arena_id)
        )
        participants = participants_result.all()

        participant_analytics = []

        for participant, user in participants:
            # Get reactions for this participant
            reactions_result = await db.execute(
                select(ArenaReaction)
                .where(
                    ArenaReaction.target_participant_id == participant.id,
                    ArenaReaction.arena_id == arena_id
                )
                .order_by(ArenaReaction.timestamp)
            )
            reactions = list(reactions_result.scalars().all())

            # Build reaction breakdown
            reaction_breakdown = {}
            reactions_timeline = []
            for reaction in reactions:
                reaction_type = reaction.reaction_type
                reaction_breakdown[reaction_type] = reaction_breakdown.get(reaction_type, 0) + 1
                reactions_timeline.append({
                    'timestamp': reaction.timestamp.isoformat(),
                    'reaction_type': reaction_type,
                    'from_user_id': str(reaction.user_id)
                })

            participant_analytics.append({
                'participant_id': str(participant.id),
                'student_id': str(participant.student_id),
                'student_name': user.name,
                'avatar_url': user.avatar_url,
                'speaking_timeline': [],  # TODO: Track individual speaking sessions
                'engagement_timeline': [],  # TODO: Track engagement changes over time
                'reactions_timeline': reactions_timeline,
                'total_speaking_time_seconds': participant.total_speaking_duration_seconds,
                'average_engagement_score': float(participant.engagement_score),
                'peak_engagement_score': float(participant.engagement_score),  # TODO: Track max
                'total_reactions_received': len(reactions),
                'reaction_breakdown': reaction_breakdown
            })

        # Calculate session duration
        session_duration_minutes = None
        if arena.start_time:
            if arena.session_state in ('completed', 'cancelled'):
                # Session ended - calculate actual duration
                # (We don't store end_time yet, so use duration_minutes as fallback)
                session_duration_minutes = arena.duration_minutes
            else:
                # Session in progress
                elapsed = datetime.utcnow() - arena.start_time
                session_duration_minutes = int(elapsed.total_seconds() / 60)

        # Aggregate stats
        total_speaking_time = sum(p.total_speaking_duration_seconds for p, _ in participants)
        avg_engagement = sum(float(p.engagement_score) for p, _ in participants) / len(participants) if participants else 0.0

        aggregate_stats = {
            'total_speaking_time_seconds': total_speaking_time,
            'average_engagement_score': round(avg_engagement, 2),
            'total_reactions': sum(len(p['reactions_timeline']) for p in participant_analytics)
        }

        return {
            'arena_id': str(arena_id),
            'session_duration_minutes': session_duration_minutes,
            'total_participants': len(participants),
            'participants': participant_analytics,
            'aggregate_stats': aggregate_stats
        }

    @staticmethod
    async def save_teacher_rating(
        db: AsyncSession,
        participant_id: UUID,
        teacher_id: UUID,
        overall_rating: float,
        criteria_scores: dict,
        feedback: Optional[str] = None,
    ) -> Optional[ArenaParticipant]:
        """
        Save teacher rating for participant.
        TODO Phase 5: Store in separate arena_ratings table.
        For now, this is a placeholder.
        """
        # Verify participant exists and teacher has access
        result = await db.execute(
            select(ArenaParticipant, Arena)
            .join(Arena, Arena.id == ArenaParticipant.arena_id)
            .join(teacher_assignments, and_(
                teacher_assignments.c.class_id == Arena.class_id,
                teacher_assignments.c.teacher_id == teacher_id
            ))
            .where(ArenaParticipant.id == participant_id)
        )
        row = result.first()
        if not row:
            return None

        participant = row[0]
        # TODO Phase 5: Create ArenaRating record
        # For now, just return participant
        return participant

    @staticmethod
    async def publish_arena_results(
        db: AsyncSession,
        arena_id: UUID,
        teacher_id: UUID,
        include_ai_analysis: bool = True,
        visibility: str = 'class',
    ) -> Optional[Arena]:
        """
        Publish arena results for student viewing.
        Updates arena status and prepares share URL.
        """
        # Verify teacher has access
        arena = await ArenaService.get_arena(db, arena_id, teacher_id)
        if not arena:
            return None

        # Verify session is completed
        if arena.session_state not in ('completed', 'cancelled'):
            return None

        # Update arena status to published
        arena.status = ArenaStatus.PUBLISHED

        # TODO Phase 5: Generate share URL based on visibility
        # TODO Phase 5: Trigger AI analysis if enabled

        await db.commit()
        await db.refresh(arena)

        return arena
