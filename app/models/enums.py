"""Centralized Enum Definitions"""

import enum


# Domain 1: Onboarding


class InquiryType(str, enum.Enum):
    """Contact inquiry types - matches frontend dropdown options"""
    PROGRAM_SELECTION_GUIDANCE = "program_selection_guidance"
    BILLING = "billing"
    DEMO_REQUEST = "demo_request"
    NEW_ONBOARDING = "new_onboarding"


class SchoolType(str, enum.Enum):
    """School education levels (primary, secondary, mixed per product)"""
    PRIMARY = "primary"
    SECONDARY = "secondary"
    MIXED = "mixed"


class ProgramType(str, enum.Enum):
    """School program types"""
    PIONEER = "pioneer"
    PARTNERSHIP = "partnership"


# Domain 2: User & Authentication


class UserRole(str, enum.Enum):
    """User roles for RBAC"""
    SCHOOL_ADMIN = "school_admin"
    TEACHER = "teacher"
    STUDENT = "student"


# Domain 3: Academic & Classroom


class ProficiencyLevel(str, enum.Enum):
    """CEFR-style proficiency levels for classrooms"""
    BEGINNER = "beginner"
    A1 = "a1"
    A2 = "a2"
    B1 = "b1"
    B2 = "b2"
    INTERMEDIATE = "intermediate"
    C1 = "c1"


class DayOfWeek(str, enum.Enum):
    """Days of the week for schedules"""
    MONDAY = "Mon"
    TUESDAY = "Tue"
    WEDNESDAY = "Wed"
    THURSDAY = "Thu"
    FRIDAY = "Fri"
    SATURDAY = "Sat"
    SUNDAY = "Sun"


class ClassStatus(str, enum.Enum):
    """Class status"""
    ACTIVE = "active"
    ARCHIVED = "archived"


class StudentRole(str, enum.Enum):
    """Student roles in classroom"""
    STUDENT = "student"
    CLASS_MONITOR = "class_monitor"
    TIME_KEEPER = "time_keeper"


# Domain 4: Curriculum


class CurriculumSourceType(str, enum.Enum):
    """Curriculum source types"""
    LIBRARY_MASTER = "library_master"
    TEACHER_UPLOAD = "teacher_upload"
    MERGED = "merged"


class CurriculumStatus(str, enum.Enum):
    """Curriculum status"""
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


# Domain 5: Assessment


class QuestionType(str, enum.Enum):
    """Question types"""
    MULTIPLE_CHOICE = "multiple_choice"
    OPEN_TEXT = "open_text"
    ORAL = "oral"
    TRUE_FALSE = "true_false"


class TaskCategory(str, enum.Enum):
    """Task category: Assessment (formal evaluation) vs Assignment (general task)"""
    ASSESSMENT = "assessment"
    ASSIGNMENT = "assignment"


class AssignmentType(str, enum.Enum):
    """Assignment types (delivery method for assessments)"""
    ORAL = "oral"
    WRITTEN = "written"


class AssignmentStatus(str, enum.Enum):
    """Assignment status"""
    DRAFT = "draft"
    PUBLISHED = "published"


class SubmissionStatus(str, enum.Enum):
    """Student submission status"""
    SUBMITTED = "submitted"
    GRADED = "graded"


# Domain 6: Arena


class ArenaStatus(str, enum.Enum):
    """Arena challenge status"""
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    LIVE = "live"
    COMPLETED = "completed"
    PUBLISHED = "published"


# Domain 7: Communication


class AnnouncementType(str, enum.Enum):
    """Announcement types"""
    ENROLLMENT = "enrollment"
    SUBMISSION = "submission"
    ARENA = "arena"
    SYSTEM = "system"
    GRADING = "grading"


class NotificationChannel(str, enum.Enum):
    """Notification delivery channels"""
    IN_APP = "IN_APP"
    EMAIL = "EMAIL"
    PUSH = "PUSH"


# Domain 8: Analytics


class SessionType(str, enum.Enum):
    """Learning session types"""
    LEARNING = "learning"
    PRACTICE = "practice"


class SessionStatus(str, enum.Enum):
    """Session status"""
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


# Domain 9: Billing


class BillStatus(str, enum.Enum):
    """Bill payment status"""
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"


# Domain 10: Admin activity log


class ActivityActionType(str, enum.Enum):
    """Types of actions recorded in the school activity log (Figma: Activity Summary row + icon)."""
    STUDENT_REGISTERED = "student_registered"
    STUDENT_REMOVED = "student_removed"
    CLASS_CREATED = "class_created"
    CLASS_ARCHIVED = "class_archived"
    TEACHER_INVITED = "teacher_invited"
    TEACHER_JOINED = "teacher_joined"
    CURRICULUM_PUBLISHED = "curriculum_published"
    ARENA_SCHEDULED = "arena_scheduled"
    ARENA_COMPLETED = "arena_completed"
    SUBMISSION = "submission"  # e.g. "John Doe submitted \"unit 3 essay\""
    RESOURCE_UPLOAD = "resource_upload"  # e.g. "You uploaded a new resource"
    CLASS_SESSION_COMPLETED = "class_session_completed"  # e.g. "Class 5B just finished ... with avg score"
    OTHER = "other"
