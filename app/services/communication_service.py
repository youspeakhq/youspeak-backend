from typing import List, Optional, Tuple
from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.logging import get_logger

logger = get_logger(__name__)

from app.models.communication import Announcement
from app.models.user import User
from app.schemas.communication import AnnouncementCreate


class CommunicationService:
    @staticmethod
    async def get_announcement_by_id(db: AsyncSession, announcement_id: UUID) -> Optional[Announcement]:
        """Fetch a single announcement by ID."""
        stmt = select(Announcement).where(Announcement.id == announcement_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def list_announcements(
        db: AsyncSession,
        school_id: UUID,
        class_id: Optional[UUID] = None,
        teacher_id: Optional[UUID] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[dict], int]:
        """
        List announcements with author names.
        Filters by school (always) and optionally by class or teacher.
        """
        stmt = (
            select(Announcement, User.first_name, User.last_name)
            .join(User, User.id == Announcement.author_id)
            .where(Announcement.school_id == school_id)
            .order_by(Announcement.created_at.desc())
        )

        if class_id:
            stmt = stmt.where(Announcement.class_id == class_id)
        
        if teacher_id:
            stmt = stmt.where(Announcement.author_id == teacher_id)

        # Count total
        count_stmt = select(func.count()).select_from(Announcement).where(Announcement.school_id == school_id)
        if class_id:
            count_stmt = count_stmt.where(Announcement.class_id == class_id)
        if teacher_id:
            count_stmt = count_stmt.where(Announcement.author_id == teacher_id)
        
        total = (await db.execute(count_stmt)).scalar() or 0

        # Paging
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(stmt)
        rows = result.all()

        items = []
        for announcement, first_name, last_name in rows:
            data = {
                "id": announcement.id,
                "author_id": announcement.author_id,
                "class_id": announcement.class_id,
                "assignment_id": announcement.assignment_id,
                "type": announcement.type,
                "message": announcement.message,
                "created_at": announcement.created_at,
                "author_name": f"{first_name or ''} {last_name or ''}".strip() or None,
            }
            items.append(data)

        return items, total

    @staticmethod
    async def create_announcement(
        db: AsyncSession,
        announcement_in: AnnouncementCreate,
        author_id: UUID
    ) -> Announcement:
        """
        Create a new announcement and associate it with classes.
        """
        logger.info(
            "announcement_creation_started",
            author_id=author_id,
            class_ids=announcement_in.class_ids
        )
        try:
            db_obj = Announcement(
                title=announcement_in.title,
                body=announcement_in.body,
                author_id=author_id,
                announcement_type=announcement_in.announcement_type,
            )
            db.add(db_obj)
            await db.flush()  # Get ID

            # Associate with classes
            if announcement_in.class_ids:
                from app.models.communication import announcement_classes
                for class_id in announcement_in.class_ids:
                    stmt = announcement_classes.insert().values(
                        announcement_id=db_obj.id,
                        class_id=class_id
                    )
                    await db.execute(stmt)

            await db.commit()
            await db.refresh(db_obj)
            logger.info("announcement_created", announcement_id=db_obj.id)
            return db_obj
        except Exception as e:
            logger.error("announcement_creation_failed", error=str(e))
            await db.rollback()
            raise

    @staticmethod
    async def delete_announcement(db: AsyncSession, announcement_id: UUID) -> bool:
        """Delete an announcement."""
        announcement = await db.get(Announcement, announcement_id)
        if not announcement:
            return False
        await db.delete(announcement)
        await db.commit()
        return True
