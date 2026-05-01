"""Arena-local enum definitions (subset of core enums needed by arena service)."""

import enum


class ArenaStatus(str, enum.Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    LIVE = "live"
    COMPLETED = "completed"
    PUBLISHED = "published"


class UserRole(str, enum.Enum):
    SCHOOL_ADMIN = "school_admin"
    TEACHER = "teacher"
    STUDENT = "student"
