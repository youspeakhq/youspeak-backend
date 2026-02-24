"""Minimal read-only refs for joins (tables owned by core)."""

from sqlalchemy import Column, Integer, String

from sqlalchemy.dialects.postgresql import UUID as PGUUID

from database import Base
from models.base import BaseModel, SchoolScopedMixin


class SchoolRef(Base):
    """Minimal ref so FK curriculums.school_id can resolve (table owned by core)."""
    __tablename__ = "schools"
    id = Column(PGUUID(as_uuid=True), primary_key=True)


class Language(BaseModel):
    __tablename__ = "languages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    code = Column(String(10), nullable=False, unique=True)


class ClassRef(BaseModel, SchoolScopedMixin):
    """Minimal class ref for curriculum-class association (id, name for response)."""
    __tablename__ = "classes"

    name = Column(String(255), nullable=False)
    sub_class = Column(String(100), nullable=True)
