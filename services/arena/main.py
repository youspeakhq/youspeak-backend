"""Main Entry Point for Arena Service"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .api.v1.endpoints import live, audio
from .websocket.connection_manager import connection_manager
from .services.audio_analysis_service import audio_analysis_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing Arena Service...")
    await connection_manager.initialize()
    
    # Set broadcast callback for AI analysis
    async def _broadcast_analysis(arena_id, data: dict):
        await connection_manager.broadcast(arena_id, data)
    
    audio_analysis_service.set_broadcast_callback(_broadcast_analysis)
    
    yield
    
    # Shutdown
    logger.info("Shutting down Arena Service...")
    await connection_manager.shutdown()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    docs_url=f"{settings.API_V1_PREFIX}/docs",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(live.router, prefix=settings.API_V1_PREFIX, tags=["live"])
app.include_router(audio.router, prefix=f"{settings.API_V1_PREFIX}/audio", tags=["audio"])


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION
    }


@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": f"Welcome to {settings.APP_NAME}"}
