from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.onboarding import School, Language, school_languages
from app.models.user import User
from app.models.enums import UserRole, SchoolType, ProgramType, ClassStatus
from app.models.academic import Class, Semester
from app.schemas.school import SchoolCreate, SchoolUpdate
from app.services.user_service import UserService

class SchoolService:
    """Service layer for School operations"""
    
    @staticmethod
    async def get_school_by_id(db: AsyncSession, school_id: UUID) -> Optional[School]:
        result = await db.execute(
            select(School).where(School.id == school_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def create_school_with_admin(
        db: AsyncSession, 
        school_data: SchoolCreate,
        admin_data: Dict[str, str]
    ) -> School:
        """
        Create a new school and its first admin user transactionally.
        """
        # Create School
        school = School(
            name=school_data.name,
            school_type=school_data.school_type,
            program_type=school_data.program_type,
            address_country=school_data.address_country,
            address_state=school_data.address_state,
            address_city=school_data.address_city,
            address_zip=school_data.address_zip,
            is_active=True
        )
        db.add(school)
        await db.flush() # Flush to get school.id
        
        # Create Admin User
        # Create Admin User
        await UserService.create_user(
            db=db,
            email=admin_data["email"],
            password=admin_data["password"],
            first_name=admin_data["first_name"],
            last_name=admin_data["last_name"],
            role=UserRole.SCHOOL_ADMIN,
            school_id=school.id
        )
        
        # Create Default Semester
        from datetime import datetime, timedelta
        default_semester = Semester(
             school_id=school.id,
             name="Term 1",
             start_date=datetime.utcnow(),
             end_date=datetime.utcnow() + timedelta(days=90),
             is_active=True
        )
        db.add(default_semester)
        
        # Seed Languages if empty
        stmt = select(Language).limit(1)
        result = await db.execute(stmt)
        if not result.scalar_one_or_none():
             languages = [
                 Language(code="en", name="English"),
                 Language(code="es", name="Spanish"),
                 Language(code="fr", name="French")
             ]
             db.add_all(languages)
        
        await db.commit()
        await db.refresh(school)
        return school

    @staticmethod
    async def update_school(
        db: AsyncSession, 
        school_id: UUID, 
        school_update: SchoolUpdate
    ) -> Optional[School]:
        school = await SchoolService.get_school_by_id(db, school_id)
        if not school:
            return None
        
        update_data = school_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(school, field, value)
            
        await db.commit()
        await db.refresh(school)
        return school
    
    @staticmethod
    async def get_stats(db: AsyncSession, school_id: UUID) -> Dict[str, int]:
        """
        Get aggregated stats for admin dashboard.
        """
        # Active Classes
        classes_query = select(func.count(Class.id)).where(
            Class.school_id == school_id,
            Class.status == ClassStatus.ACTIVE
        )
        classes_count = await db.scalar(classes_query)
        
        # Total Students
        students_query = select(func.count(User.id)).where(
            User.school_id == school_id,
            User.role == UserRole.STUDENT,
            User.is_active == True,
            User.deleted_at.is_(None)
        )
        students_count = await db.scalar(students_query)
        
        # Total Teachers
        teachers_query = select(func.count(User.id)).where(
            User.school_id == school_id,
            User.role == UserRole.TEACHER,
            User.is_active == True,
            User.deleted_at.is_(None)
        )
        teachers_count = await db.scalar(teachers_query)
        
        return {
            "active_classes": classes_count or 0,
            "total_students": students_count or 0,
            "total_teachers": teachers_count or 0
        }

    @staticmethod
    async def update_programs(db: AsyncSession, school_id: UUID, language_codes: List[str]) -> bool:
        """Update languages offered by school"""
        school = await SchoolService.get_school_by_id(db, school_id)
        if not school:
            return False
            
        # Get language objects
        stmt = select(Language).where(Language.code.in_(language_codes))
        result = await db.execute(stmt)
        languages = result.scalars().all()
        
        # Update relationship
        # Note: This might need more careful handling if preserving existing ones
        # For now, we replace
        school.languages = list(languages)
        await db.commit()
        return True
    
    @staticmethod
    async def get_semesters(db: AsyncSession, school_id: UUID) -> List[Semester]:
        """Get all semesters for school"""
        stmt = select(Semester).where(Semester.school_id == school_id).order_by(desc(Semester.start_date))
        result = await db.execute(stmt)
        return list(result.scalars().all())
