from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from sqlalchemy import select, func, delete, insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.curriculum import Curriculum
from app.models.academic import Class, curriculum_classes
from app.models.onboarding import Language
from app.models.enums import CurriculumStatus, CurriculumSourceType
from app.schemas.content import CurriculumCreate, CurriculumUpdate

class CurriculumService:
    @staticmethod
    async def get_curriculums(
        db: AsyncSession, 
        school_id: UUID, 
        skip: int = 0, 
        limit: int = 100,
        status: Optional[CurriculumStatus] = None,
        language_id: Optional[int] = None,
        search: Optional[str] = None
    ) -> tuple[List[Curriculum], int]:
        """Get paginated curriculums for a school with filters."""
        query = (
            select(Curriculum)
            .where(Curriculum.school_id == school_id)
            .options(
                selectinload(Curriculum.classes),
                selectinload(Curriculum.language)
            )
        )
        
        if status:
            query = query.where(Curriculum.status == status)
        if language_id:
            query = query.where(Curriculum.language_id == language_id)
        if search:
            query = query.where(Curriculum.title.ilike(f"%{search}%"))
            
        # Count
        count_stmt = select(func.count()).select_from(query.subquery())
        total = (await db.execute(count_stmt)).scalar_one()
        
        # Paginate
        result = await db.execute(query.offset(skip).limit(limit).order_by(Curriculum.created_at.desc()))
        return list(result.scalars().all()), total

    @staticmethod
    async def get_curriculum_by_id(db: AsyncSession, curriculum_id: UUID, school_id: UUID) -> Optional[Curriculum]:
        """Get a specific curriculum and ensure it belongs to the school."""
        result = await db.execute(
            select(Curriculum)
            .where(Curriculum.id == curriculum_id, Curriculum.school_id == school_id)
            .options(
                selectinload(Curriculum.classes),
                selectinload(Curriculum.language)
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create_curriculum(
        db: AsyncSession, 
        school_id: UUID, 
        curriculum_in: CurriculumCreate,
        file_url: Optional[str] = None
    ) -> Curriculum:
        """Create a new curriculum and link to classes."""
        new_curriculum = Curriculum(
            school_id=school_id,
            title=curriculum_in.title,
            description=curriculum_in.description,
            language_id=curriculum_in.language_id,
            source_type=curriculum_in.source_type,
            file_url=file_url,
            status=CurriculumStatus.PUBLISHED # Default to published if file exists, or adjust per logic
        )
        db.add(new_curriculum)
        await db.flush()

        if curriculum_in.class_ids:
            # Batch insert class links
            for class_id in curriculum_in.class_ids:
                stmt = insert(curriculum_classes).values(
                    curriculum_id=new_curriculum.id,
                    class_id=class_id
                )
                await db.execute(stmt)

        await db.commit()
        await db.refresh(new_curriculum)
        
        # Re-fetch with relationships
        return await CurriculumService.get_curriculum_by_id(db, new_curriculum.id, school_id)

    @staticmethod
    async def update_curriculum(
        db: AsyncSession,
        curriculum_id: UUID,
        school_id: UUID,
        curriculum_update: CurriculumUpdate
    ) -> Optional[Curriculum]:
        """Update curriculum details and class assignments."""
        curriculum = await CurriculumService.get_curriculum_by_id(db, curriculum_id, school_id)
        if not curriculum:
            return None

        update_data = curriculum_update.model_dump(exclude_unset=True)
        class_ids = update_data.pop("class_ids", None)

        for field, value in update_data.items():
            setattr(curriculum, field, value)

        if class_ids is not None:
            # Sync classes: remove all, then add new ones
            await db.execute(
                delete(curriculum_classes).where(curriculum_classes.c.curriculum_id == curriculum_id)
            )
            for cid in class_ids:
                await db.execute(
                    insert(curriculum_classes).values(curriculum_id=curriculum_id, class_id=cid)
                )

        await db.commit()
        await db.refresh(curriculum)
        return curriculum

    @staticmethod
    async def delete_curriculum(db: AsyncSession, curriculum_id: UUID, school_id: UUID) -> bool:
        """Delete a curriculum."""
        curriculum = await CurriculumService.get_curriculum_by_id(db, curriculum_id, school_id)
        if not curriculum:
            return False
        
        await db.delete(curriculum)
        await db.commit()
        return True

    @staticmethod
    async def merge_curriculum(
        db: AsyncSession,
        curriculum_id: UUID,
        school_id: UUID,
        strategy: str = "append"
    ) -> Optional[Curriculum]:
        """
        Specialized logic to merge teacher content with inbuilt library.
        For now, this is a placeholder that updates the source_type or duplicates content.
        """
        curriculum = await CurriculumService.get_curriculum_by_id(db, curriculum_id, school_id)
        if not curriculum:
            return None
            
        # Mock logic: Create a new merged entry or update existing
        # In a real scenario, this would involve processing file contents or database records
        curriculum.source_type = CurriculumSourceType.MERGED
        curriculum.title = f"{curriculum.title} (Merged)"
        
        await db.commit()
        await db.refresh(curriculum)
        return curriculum
