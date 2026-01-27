"""API V1 Router"""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, users

# Create API v1 router
api_router = APIRouter()

# Include endpoint routers
api_router.include_router(auth.router)
api_router.include_router(users.router)
