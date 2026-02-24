"""Database connection and session management."""

import re
import ssl
import sys

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool
from typing import AsyncGenerator, Tuple

from config import settings


def get_async_engine_url_and_connect_args() -> Tuple[str, dict]:
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

is_testing = "pytest" in sys.modules

engine_kwargs = {
    "connect_args": connect_args,
    "echo": False,
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

engine = create_async_engine(database_url, **engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def close_db() -> None:
    await engine.dispose()
