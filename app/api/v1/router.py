"""API V1 Router"""

from fastapi import APIRouter

# Import endpoint routers
from app.api.v1.endpoints import (
    auth, users, schools, admin, students,
    teachers, classes, classrooms, references,
    curriculums
)

# Create API v1 router
api_router = APIRouter()

# Include endpoint routers with prefixes and tags
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(schools.router, prefix="/schools", tags=["School Configuration"])
api_router.include_router(admin.router, prefix="/admin", tags=["Admin Dashboard"])
api_router.include_router(students.router, prefix="/students", tags=["Student Management"])
api_router.include_router(teachers.router, prefix="/teachers", tags=["Teacher Management"])
api_router.include_router(classes.router, prefix="/my-classes", tags=["Teacher Classroom"])
api_router.include_router(classrooms.router, prefix="/classrooms", tags=["Classrooms (Admin)"])
api_router.include_router(references.router, prefix="/references", tags=["References"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(curriculums.router, prefix="/curriculums", tags=["Curriculum"])
