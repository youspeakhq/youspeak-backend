"""Curriculum and Topic models; curriculum_classes association table."""

import models.refs  # noqa: F401 - ensure schools/languages in metadata for FK resolution

from sqlalchemy import Column, String, Text, ForeignKey, Float, Integer, Table
from sqlalchemy.dialects.postgresql import UUID, ENUM, JSONB
from sqlalchemy.orm import relationship

from database import Base
from models.base import BaseModel, SchoolScopedMixin
from models.enums import CurriculumSourceType, CurriculumStatus


class Curriculum(BaseModel, SchoolScopedMixin):
    __tablename__ = "curriculums"

    language_id = Column(ForeignKey("languages.id", ondelete="RESTRICT"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    source_type = Column(ENUM(CurriculumSourceType, name="curriculum_source_type"), nullable=False)
    file_url = Column(Text, nullable=True)
    status = Column(
        ENUM(CurriculumStatus, name="curriculum_status"),
        default=CurriculumStatus.DRAFT,
        nullable=False,
        index=True,
    )

    language = relationship("Language", backref="curriculums")
    classes = relationship(
        "ClassRef",
        secondary="curriculum_classes",
        backref="curriculums",
    )
    topics = relationship(
        "Topic",
        back_populates="curriculum",
        cascade="all, delete-orphan",
        order_by="Topic.order_index",
    )


class Topic(BaseModel):
    __tablename__ = "topics"

    curriculum_id = Column(UUID(as_uuid=True), ForeignKey("curriculums.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=True)
    duration_hours = Column(Float, nullable=True)
    learning_objectives = Column(JSONB, default=list, nullable=False)
    order_index = Column(Integer, default=0, nullable=False)

    curriculum = relationship("Curriculum", back_populates="topics")


curriculum_classes = Table(
    "curriculum_classes",
    Base.metadata,
    Column("curriculum_id", UUID(as_uuid=True), ForeignKey("curriculums.id", ondelete="CASCADE"), primary_key=True),
    Column("class_id", UUID(as_uuid=True), ForeignKey("classes.id", ondelete="CASCADE"), primary_key=True),
)
