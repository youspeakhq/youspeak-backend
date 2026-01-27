"""Domain 4: Curriculum & Content Model"""

from sqlalchemy import Column, String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, ENUM
from sqlalchemy.orm import relationship

from app.models.base import BaseModel
from app.models.enums import CurriculumSourceType, CurriculumStatus


class Curriculum(BaseModel):
    """
    Content/Curriculum management with merge logic support.
    Supports library content, teacher uploads, and merged versions.
    """
    __tablename__ = "curriculums"
    
    # Foreign Keys
    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id", ondelete="CASCADE"), nullable=True, index=True)
    language_id = Column(ForeignKey("languages.id", ondelete="RESTRICT"), nullable=False, index=True)
    
    # Content Details
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    source_type = Column(ENUM(CurriculumSourceType, name="curriculum_source_type"), nullable=False)
    file_url = Column(Text, nullable=True)  # Original source file
    status = Column(ENUM(CurriculumStatus, name="curriculum_status"), default=CurriculumStatus.DRAFT, nullable=False, index=True)
    
    # Relationships
    class_ = relationship("Class", back_populates="curriculums")
    language = relationship("Language", back_populates="curriculums")
    
    def __repr__(self) -> str:
        return f"<Curriculum {self.title} ({self.source_type})>"
