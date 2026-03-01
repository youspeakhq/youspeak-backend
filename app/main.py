"""FastAPI Application Entry Point"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from sqlalchemy import text

from app.config import settings
from app.database import init_db, close_db, engine
from app.core.logging import setup_logging, get_logger
from app.core.middleware import (
    RequestIDMiddleware,
    RequestTimingMiddleware,
    SecurityHeadersMiddleware
)
from app.api.v1.router import api_router

# Setup logging
setup_logging()
logger = get_logger(__name__)


# Rate limiter
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting application", extra={"environment": settings.ENVIRONMENT})

    # Initialize database (for development only - use Alembic in production)
    if settings.is_development:
        await init_db()
        logger.info("Database initialized")

    # Curriculum service HTTP client (internal proxy)
    app.state.curriculum_http = None
    if settings.CURRICULUM_SERVICE_URL:
        import httpx
        app.state.curriculum_http = httpx.AsyncClient(
            base_url=settings.CURRICULUM_SERVICE_URL.rstrip("/"),
            timeout=120.0,
        )

    yield

    # Shutdown
    logger.info("Shutting down application")
    if getattr(app.state, "curriculum_http", None) is not None:
        await app.state.curriculum_http.aclose()
    await close_db()


# Create FastAPI app
app = FastAPI(
    title="YouSpeak Platform API",
    version="1.0.0",
    description="Backend API for YouSpeak Education Platform",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/api/v1/openapi.json",
    lifespan=lifespan,
)

# Add rate limiting state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=settings.ALLOWED_METHODS,
    allow_headers=[settings.ALLOWED_HEADERS],
    expose_headers=["X-Request-ID", "X-Process-Time"],
)

# Custom middleware
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestTimingMiddleware)
app.add_middleware(RequestIDMiddleware)

# Include API router
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


# Health check endpoints
@app.get("/health", tags=["Health"])
async def health_check():
    """Basic health check endpoint"""
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT
    }


@app.get("/health/ready", tags=["Health"])
async def health_ready():
    """Readiness: checks database connectivity. Returns 503 if DB is unreachable."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "database": "connected",
        }
    except Exception as e:
        logger.exception("Database health check failed")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "database": "disconnected",
                "detail": str(e),
            },
        )


@app.get("/", include_in_schema=False)
async def root():
    """Root endpoint - Redirects to docs"""
    return RedirectResponse(url="/docs")


# Exception handlers: return standardized error envelope for integration tests / clients
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Return { success: false, error: { code, message } } so clients can use error.message."""
    detail = exc.detail
    if isinstance(detail, dict):
        message = detail.get("message", detail.get("detail", str(detail)))
    else:
        message = str(detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            # Keep legacy 'detail' key so existing tests and clients that
            # inspect response["detail"] continue to work, while also
            # providing a structured error envelope.
            "detail": message,
            "error": {"code": f"HTTP_{exc.status_code}", "message": message},
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors"""
    logger.warning(
        "Validation error",
        extra={
            "path": request.url.path,
            "errors": exc.errors(),
            "correlation_id": getattr(request.state, "request_id", None),
        }
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": exc.errors(),
            "body": exc.body
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions"""
    logger.error(
        f"Unhandled exception: {str(exc)}",
        extra={
            "path": request.url.path,
            "correlation_id": getattr(request.state, "request_id", None),
        },
        exc_info=True
    )
    detail = "Internal server error"
    if settings.ENVIRONMENT.lower() == "test":
        detail = f"{detail}: {type(exc).__name__}: {exc}"
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": detail},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )
