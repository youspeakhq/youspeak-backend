"""Database Connection and Session Management"""

import re
import ssl

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from typing import AsyncGenerator

from app.config import settings

# Convert postgresql:// to postgresql+asyncpg:// for async support
database_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

# asyncpg uses ssl=SSLContext or True, not sslmode; strip sslmode from URL (asyncpg#737, SQLAlchemy#6275)
# RDS uses a cert that can cause CERTIFICATE_VERIFY_FAILED; use a context that encrypts but does not verify
connect_args = {}
if re.search(r"[?&]sslmode=(require|required|verify-full)", database_url, re.I):
    _ssl_ctx = ssl.create_default_context()
    _ssl_ctx.check_hostname = False
    _ssl_ctx.verify_mode = ssl.CERT_NONE
    connect_args["ssl"] = _ssl_ctx
    database_url = re.sub(r"[?&]sslmode=[^&]+", "", database_url, flags=re.I)
    database_url = re.sub(r"\?&", "?", database_url).rstrip("?")
if "?&" in database_url:
    database_url = database_url.replace("?&", "?")

# Create async engine with connection pooling (pool_pre_ping detects stale RDS connections)
engine = create_async_engine(
    database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
    echo=settings.DEBUG,
    future=True,
)

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
