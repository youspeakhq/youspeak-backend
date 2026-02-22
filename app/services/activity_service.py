"""Service for admin activity log: list and create."""

from typing import Optional
from uuid import UUID

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.activity_log import ActivityLog
from app.models.user import User
from app.models.enums import ActivityActionType
from app.schemas.admin import ActivityLogCreate


class ActivityService:
    @staticmethod
    async def list_activity(
        db: AsyncSession,
        school_id: UUID,
        page: int = 1,
        page_size: int = 20,
        action_type: Optional[ActivityActionType] = None,
    ) -> tuple[list[dict], int]:
        """
        List activity log entries for the school (newest first).
        Returns (list of ActivityLogOut-compatible dicts, total count).
        """
        q = select(ActivityLog).where(ActivityLog.school_id == school_id)
        if action_type is not None:
            q = q.where(ActivityLog.action_type == action_type)

        count_stmt = select(func.count(ActivityLog.id)).where(ActivityLog.school_id == school_id)
        if action_type is not None:
            count_stmt = count_stmt.where(ActivityLog.action_type == action_type)
        total = await db.scalar(count_stmt) or 0

        stmt = (
            q.options(selectinload(ActivityLog.performed_by))
            .order_by(desc(ActivityLog.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await db.execute(stmt)
        rows = result.scalars().all()

        out = []
        for log in rows:
            performer_name = None
            if log.performed_by is not None:
                performer_name = log.performed_by.full_name
            out.append({
                "id": log.id,
                "action_type": log.action_type,
                "description": log.description,
                "performed_by_user_id": log.performed_by_user_id,
                "performer_name": performer_name,
                "target_entity_type": log.target_entity_type,
                "target_entity_id": log.target_entity_id,
                "created_at": log.created_at,
            })
        return out, total

    @staticmethod
    async def create(
        db: AsyncSession,
        school_id: UUID,
        payload: ActivityLogCreate,
        performed_by_user_id: Optional[UUID] = None,
    ) -> ActivityLog:
        """Append an activity log entry. Optionally set performed_by to current user."""
        log = ActivityLog(
            school_id=school_id,
            action_type=payload.action_type,
            description=payload.description,
            performed_by_user_id=performed_by_user_id,
            target_entity_type=payload.target_entity_type,
            target_entity_id=payload.target_entity_id,
            metadata_=payload.metadata,
        )
        db.add(log)
        await db.commit()
        await db.refresh(log)
        return log
