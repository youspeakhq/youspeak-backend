"""Service for school billing: list bills."""

from uuid import UUID

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import Bill


class BillingService:
    @staticmethod
    async def list_bills(
        db: AsyncSession,
        school_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Bill], int]:
        """
        List bills for the school (newest first by due_date then created_at).
        Returns (list of Bill, total count).
        """
        count_stmt = select(func.count(Bill.id)).where(Bill.school_id == school_id)
        total = await db.scalar(count_stmt) or 0

        stmt = (
            select(Bill)
            .where(Bill.school_id == school_id)
            .order_by(desc(Bill.due_date), desc(Bill.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await db.execute(stmt)
        rows = result.scalars().all()
        return list(rows), total
