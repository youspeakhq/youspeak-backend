"""Models Package - Export all models for easy imports"""

from app.models.base import BaseModel, SchoolScopedMixin, SoftDeleteMixin, StatusMixin
from app.models.enums import *
from app.models.onboarding import ContactInquiry, School, Language, school_languages
from app.models.user import User
from app.models.academic import Semester, Class, ClassSchedule, ClassEnrollment, TeacherAssignment
from app.models.curriculum import Curriculum
from app.models.assessment import Question, Assignment, AssignmentQuestion, StudentSubmission, assignment_classes
from app.models.arena import Arena, ArenaCriteria, ArenaRule, ArenaPerformer, arena_moderators
from app.models.communication import Announcement, AnnouncementReminder
from app.models.analytics import LearningSession, Award
from app.models.billing import Bill

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
    "Semester",
    "Class",
    "ClassSchedule",
    "ClassEnrollment",
    "TeacherAssignment",
    
    # Curriculum
    "Curriculum",
    
    # Assessment
    "Question",
    "Assignment",
    "AssignmentQuestion",
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
]
