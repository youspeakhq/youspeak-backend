"""Curriculum service FastAPI app."""

# CI: changes here trigger curriculum image build (linux/amd64) and push to ECR

from contextlib import asynccontextmanager
from sqlalchemy import text

from fastapi import FastAPI

from config import settings
from database import engine, get_db, close_db
from api.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_db()


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.1",
    lifespan=lifespan,
)

app.include_router(router, prefix="/curriculums", tags=["Curriculum"])


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "environment": settings.ENVIRONMENT,
    }


@app.get("/health/ready")
async def health_ready():
    from fastapi.responses import JSONResponse
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "database": "disconnected", "detail": str(e)},
        )
