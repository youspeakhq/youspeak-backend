"""Base Models and Mixins for DRY principles"""

import uuid
from datetime import datetime
from sqlalchemy import Column, DateTime, String, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declared_attr

from app.database import Base


class BaseModel(Base):
    """
    Base model class with common fields for all models.
    
    Provides:
    - UUID primary key
    - created_at timestamp
    - updated_at timestamp
    """
    __abstract__ = True
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class SchoolScopedMixin:
    """
    Mixin for multi-tenant models scoped to a school.
    
    Provides:
    - school_id foreign key
    - Relationship to school (configured in concrete models)
    """
    
    @declared_attr
    def school_id(cls):
        return Column(
            UUID(as_uuid=True),
            ForeignKey("schools.id", ondelete="CASCADE"),
            nullable=False,
            index=True
        )


class SoftDeleteMixin:
    """
    Mixin for soft delete functionality.
    
    Provides:
    - deleted_at timestamp (NULL = active, NOT NULL = deleted)
    """
    deleted_at = Column(DateTime, nullable=True, index=True)
    
    def soft_delete(self):
        """Mark record as deleted without removing from database"""
        self.deleted_at = datetime.utcnow()
    
    def restore(self):
        """Restore a soft-deleted record"""
        self.deleted_at = None
    
    @property
    def is_deleted(self) -> bool:
        """Check if record is soft-deleted"""
        return self.deleted_at is not None


class StatusMixin:
    """
    Mixin for models with active/inactive status.
    
    Provides:
    - is_active boolean flag
    """
    is_active = Column(Boolean, default=True, nullable=False, index=True)
