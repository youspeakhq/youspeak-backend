"""Models Package - Export all models for easy imports"""

from app.models.base import BaseModel, SchoolScopedMixin, SoftDeleteMixin, StatusMixin
from app.models.enums import *
from app.models.onboarding import ContactInquiry, School, Language, school_languages
from app.models.user import User
from app.models.academic import (
    Classroom,
    Semester,
    Class,
    ClassSchedule,
    class_enrollments,
    teacher_assignments,
    classroom_teachers,
    classroom_students,
)

from app.models.curriculum import Curriculum
from app.models.assessment import Question, Assignment, assignment_questions, StudentSubmission, assignment_classes
from app.models.arena import Arena, ArenaCriteria, ArenaRule, ArenaPerformer, arena_moderators
from app.models.communication import Announcement, AnnouncementReminder
from app.models.analytics import LearningSession, Award
from app.models.billing import Bill
from app.models.access_code import TeacherAccessCode
from app.models.student_trash import StudentTrash


__all__ = [
    # Base classes
    "BaseModel",
    "SchoolScopedMixin",
    "SoftDeleteMixin",
    "StatusMixin",
    
    # Onboarding
    "ContactInquiry",
    "School",
    "Language",
    "school_languages",
    
    # User
    "User",
    
    # Academic
    "Classroom",
    "Semester",
    "Class",
    "ClassSchedule",
    "class_enrollments",
    "teacher_assignments",
    "classroom_teachers",
    "classroom_students",
    
    # Curriculum
    "Curriculum",
    
    # Assessment
    "Question",
    "Assignment",
    "assignment_questions",
    "StudentSubmission",
    "assignment_classes",
    
    # Arena
    "Arena",
    "ArenaCriteria",
    "ArenaRule",
    "ArenaPerformer",
    "arena_moderators",
    
    # Communication
    "Announcement",
    "AnnouncementReminder",
    
    # Analytics
    "LearningSession",
    "Award",
    
    # Billing
    "Bill",
    
    # Access Codes
    "TeacherAccessCode",
    
    # Trash
    "StudentTrash",
]
