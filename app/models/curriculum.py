"""Domain 4: Curriculum & Content Model"""

from sqlalchemy import Column, String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, ENUM
from sqlalchemy.orm import relationship

from app.models.base import BaseModel, SchoolScopedMixin
from app.models.enums import CurriculumSourceType, CurriculumStatus


class Curriculum(BaseModel, SchoolScopedMixin):
    """
    Content/Curriculum management with merge logic support.
    Supports library content, teacher uploads, and merged versions.
    """
    __tablename__ = "curriculums"
    
    # Foreign Keys
    language_id = Column(ForeignKey("languages.id", ondelete="RESTRICT"), nullable=False, index=True)
    
    # Content Details
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    source_type = Column(ENUM(CurriculumSourceType, name="curriculum_source_type"), nullable=False)
    file_url = Column(Text, nullable=True)  # Original source file
    status = Column(ENUM(CurriculumStatus, name="curriculum_status"), default=CurriculumStatus.DRAFT, nullable=False, index=True)
    
    # Relationships
    language = relationship("Language", back_populates="curriculums")
    classes = relationship(
        "Class",
        secondary="curriculum_classes",
        back_populates="curriculums"
    )
    school = relationship("School", back_populates="curriculums")
    
    def __repr__(self) -> str:
        return f"<Curriculum {self.title} ({self.source_type})>"
