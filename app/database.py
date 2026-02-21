"""Database Connection and Session Management"""

import re
import ssl

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from typing import AsyncGenerator, Tuple

from app.config import settings


def get_async_engine_url_and_connect_args() -> Tuple[str, dict]:
    """Return (async URL, connect_args) for SQLAlchemy async engine (app and Alembic)."""
    url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    args: dict = {}
    if re.search(r"[?&]sslmode=(require|required|verify-full)", url, re.I):
        _ctx = ssl.create_default_context()
        _ctx.check_hostname = False
        _ctx.verify_mode = ssl.CERT_NONE
        args["ssl"] = _ctx
        url = re.sub(r"[?&]sslmode=[^&]+", "", url, flags=re.I)
        url = re.sub(r"\?&", "?", url).rstrip("?")
    if "?&" in url:
        url = url.replace("?&", "?")
    return url, args


database_url, connect_args = get_async_engine_url_and_connect_args()

import sys
from sqlalchemy.pool import NullPool

# Detect if we're running tests to avoid async loop connection pool leaks
is_testing = "pytest" in sys.modules

engine_kwargs = {
    "connect_args": connect_args,
    "echo": settings.DEBUG,
    "future": True,
}

if is_testing:
    engine_kwargs["poolclass"] = NullPool
else:
    engine_kwargs.update({
        "pool_pre_ping": True,
        "pool_size": settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_MAX_OVERFLOW,
        "pool_timeout": settings.DB_POOL_TIMEOUT,
        "pool_recycle": settings.DB_POOL_RECYCLE,
    })

# Create async engine
engine = create_async_engine(database_url, **engine_kwargs)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Base class for declarative models
Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency function to get database session.
    
    Yields:
        AsyncSession: Database session
        
    Example:
        ```python
        @app.get("/users")
        async def get_users(db: AsyncSession = Depends(get_db)):
            # Use db session here
            pass
        ```
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables (for development only)"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connections"""
    await engine.dispose()
