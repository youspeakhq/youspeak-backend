"""Domain 4: Curriculum & Content Model"""

from sqlalchemy import Column, String, Text, ForeignKey, Float, Integer
from sqlalchemy.dialects.postgresql import UUID, ENUM, JSONB
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
    topics = relationship("Topic", back_populates="curriculum", cascade="all, delete-orphan", order_by="Topic.order_index")
    
    def __repr__(self) -> str:
        return f"<Curriculum {self.title} ({self.source_type})>"

class Topic(BaseModel):
    """
    Individual lesson or module within a Curriculum.
    Extracted by AI or manually created.
    """
    __tablename__ = "topics"
    
    curriculum_id = Column(UUID(as_uuid=True), ForeignKey("curriculums.id", ondelete="CASCADE"), nullable=False, index=True)
    
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=True)
    duration_hours = Column(Float, nullable=True) # Duration in hours
    learning_objectives = Column(JSONB, default=list, nullable=False) # List of strings
    order_index = Column(Integer, default=0, nullable=False) # Sequence within the curriculum
    
    curriculum = relationship("Curriculum", back_populates="topics")

    def __repr__(self) -> str:
        return f"<Topic {self.order_index}: {self.title}>"
