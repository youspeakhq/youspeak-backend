"""Curriculum enums."""

import enum


class CurriculumSourceType(str, enum.Enum):
    LIBRARY_MASTER = "library_master"
    TEACHER_UPLOAD = "teacher_upload"
    MERGED = "merged"


class CurriculumStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"
