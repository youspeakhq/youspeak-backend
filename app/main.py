"""FastAPI Application Entry Point"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import ValidationError as PydanticValidationError
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from sqlalchemy import text

from app.config import settings
from app.database import init_db, close_db, engine
from app.core.logging import setup_logging, get_logger
from app.core.rate_limit import limiter
from app.core.middleware import (
    RequestIDMiddleware,
    RequestTimingMiddleware,
    SecurityHeadersMiddleware
)
from app.api.v1.router import api_router
from app.websocket.arena_connection_manager import connection_manager

# Setup logging
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting application", extra={"environment": settings.ENVIRONMENT})

    # Initialize database (for development only - use Alembic in production)
    if settings.is_development:
        await init_db()
        logger.info("Database initialized")

    # Initialize WebSocket connection manager with Redis
    connection_manager.redis_url = settings.REDIS_URL
    await connection_manager.initialize()
    logger.info("WebSocket connection manager initialized")

    # Validate Azure Speech credentials — audio analysis is silently disabled if these are missing.
    if not settings.AZURE_SPEECH_KEY:
        logger.warning(
            "AZURE_SPEECH_KEY not configured — student pronunciation analysis will be disabled. "
            "Set AZURE_SPEECH_KEY and AZURE_SPEECH_REGION to enable real-time AI feedback."
        )
    else:
        logger.info("Azure Speech configured", extra={"region": settings.AZURE_SPEECH_REGION})

    # Ensure transcription is enabled on both RTK presets (group_call_host + group_call_participant).
    # This is idempotent — safe to run on every startup. Without this, the teacher's speech
    # (host preset) is never transcribed and no transcript events fire on the client SDK.
    from app.services.cloudflare_realtimekit_service import realtimekit_service
    try:
        enabled = await realtimekit_service.enable_transcription_on_presets()
        if enabled:
            logger.info("RTK transcription presets configured successfully")
        else:
            logger.warning("RTK transcription preset configuration had partial failures — check RTK credentials and preset IDs")
    except Exception as e:
        logger.warning(f"Could not configure RTK transcription presets: {e} — teacher transcription may not work")

    # Curriculum service HTTP client (internal proxy)
    app.state.curriculum_http = None
    if settings.CURRICULUM_SERVICE_URL:
        import httpx
        # Reduced timeout from 120s to 30s to fail faster and prevent 504 Gateway Timeouts
        # ALB/nginx typically timeout at 60s, so we fail before that
        app.state.curriculum_http = httpx.AsyncClient(
            base_url=settings.CURRICULUM_SERVICE_URL.rstrip("/"),
            timeout=30.0,
        )

    yield

    # Shutdown
    logger.info("Shutting down application")
    if getattr(app.state, "curriculum_http", None) is not None:
        await app.state.curriculum_http.aclose()
    await connection_manager.shutdown()
    await close_db()


# Create FastAPI app
app = FastAPI(
    title="YouSpeak Platform API",
    version="1.0.12",
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
    allow_origin_regex=settings.ALLOWED_ORIGINS_REGEX,
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

    def make_json_serializable(obj):
        """Convert any object to a JSON-serializable form."""
        try:
            if obj is None or isinstance(obj, (str, int, float, bool)):
                return obj
            if isinstance(obj, (list, tuple)):
                return [make_json_serializable(item) for item in obj]
            if isinstance(obj, dict):
                return {k: make_json_serializable(v) for k, v in obj.items()}
            return str(obj)
        except Exception:
            return "<non-serializable>"

    # Clean up error dicts to remove non-JSON-serializable objects (like ValueError in ctx)
    errors = []
    try:
        for error in exc.errors():
            try:
                clean_error = {
                    "type": make_json_serializable(error.get("type")),
                    "loc": make_json_serializable(error.get("loc")),
                    "msg": make_json_serializable(error.get("msg")),
                }
                if "input" in error:
                    try:
                        input_val = error["input"]
                        if isinstance(input_val, (str, int, float, bool, type(None))) or \
                           (isinstance(input_val, (list, dict)) and len(str(input_val)) < 200):
                            clean_error["input"] = make_json_serializable(input_val)
                    except Exception:
                        pass

                # Convert ctx values to strings (THIS FIXES THE ValueError SERIALIZATION BUG)
                if "ctx" in error:
                    try:
                        clean_error["ctx"] = make_json_serializable(error["ctx"])
                    except Exception:
                        pass

                errors.append(clean_error)
            except Exception:
                errors.append({
                    "type": "validation_error",
                    "msg": str(error.get("msg", "Validation failed")),
                })
    except Exception:
        errors = [{"type": "validation_error", "msg": "Validation failed"}]

    logger.warning(
        "Validation error",
        extra={
            "path": request.url.path,
            "error_count": len(errors),
            "correlation_id": getattr(request.state, "request_id", None),
        }
    )

    # Handle FormData or other non-serializable body types
    body_value = exc.body
    if not isinstance(body_value, (dict, list, str, int, float, bool, type(None))):
        body_value = str(body_value)

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": errors,  # Use cleaned errors, not exc.errors()
            "body": body_value
        },
    )


@app.exception_handler(PydanticValidationError)
async def pydantic_validation_exception_handler(request: Request, exc: PydanticValidationError):
    """
    Handle Pydantic ValidationError raised from field validators.
    Converts to 422 response like FastAPI's RequestValidationError handler.
    """
    import json

    def make_json_serializable(obj):
        """Convert any object to a JSON-serializable form."""
        try:
            if obj is None or isinstance(obj, (str, int, float, bool)):
                return obj
            if isinstance(obj, (list, tuple)):
                return [make_json_serializable(item) for item in obj]
            if isinstance(obj, dict):
                return {k: make_json_serializable(v) for k, v in obj.items()}
            # For any other type (ValueError, custom objects, etc.), convert to string
            return str(obj)
        except Exception:
            return "<non-serializable>"

    # Clean up error dicts to remove non-JSON-serializable objects
    errors = []
    try:
        for error in exc.errors():
            try:
                clean_error = {
                    "type": make_json_serializable(error.get("type")),
                    "loc": make_json_serializable(error.get("loc")),
                    "msg": make_json_serializable(error.get("msg")),
                }
                # Only include input if it's small and serializable
                if "input" in error:
                    try:
                        input_val = error["input"]
                        # Only include simple inputs, skip large or complex objects
                        if isinstance(input_val, (str, int, float, bool, type(None))) or \
                           (isinstance(input_val, (list, dict)) and len(str(input_val)) < 200):
                            clean_error["input"] = make_json_serializable(input_val)
                    except Exception:
                        pass  # Skip input if serialization fails

                # Convert ctx values to strings if present
                if "ctx" in error:
                    try:
                        clean_error["ctx"] = make_json_serializable(error["ctx"])
                    except Exception:
                        pass  # Skip ctx if serialization fails

                errors.append(clean_error)
            except Exception:
                # Fallback for individual error processing failures
                errors.append({
                    "type": "validation_error",
                    "msg": str(error.get("msg", "Validation failed")),
                })
    except Exception:
        # Ultimate fallback if exc.errors() itself fails
        errors = [{"type": "validation_error", "msg": "Validation failed"}]

    logger.warning(
        "Pydantic validation error",
        extra={
            "path": request.url.path,
            "error_count": len(errors),
            "correlation_id": getattr(request.state, "request_id", None),
        }
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": errors
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
