"""Base models and mixins."""

import uuid
from sqlalchemy import Column, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declared_attr

from database import Base
from utils.time import get_utc_now


class BaseModel(Base):
    __abstract__ = True

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    created_at = Column(DateTime, default=get_utc_now, nullable=False)
    updated_at = Column(DateTime, default=get_utc_now, onupdate=get_utc_now, nullable=False)


class SchoolScopedMixin:
    @declared_attr
    def school_id(cls):
        return Column(
            UUID(as_uuid=True),
            ForeignKey("schools.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
