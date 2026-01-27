"""Alembic Environment Configuration"""

import asyncio
import sys
from pathlib import Path
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

# Import your models here
from app.database import Base
from app.models.user import User  # noqa
from app.models.onboarding import School, Language, ContactInquiry  # noqa
from app.models.academic import Semester, Class, ClassSchedule  # noqa
from app.models.curriculum import Curriculum  # noqa
from app.models.assessment import Question, Assignment, StudentSubmission  # noqa
from app.models.arena import Arena, ArenaCriteria, ArenaRule, ArenaPerformer  # noqa
from app.models.communication import Announcement, AnnouncementReminder  # noqa
from app.models.analytics import LearningSession, Award  # noqa
from app.models.billing import Bill  # noqa
from app.config import settings

# This is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Add your model's MetaData object here for 'autogenerate' support
target_metadata = Base.metadata

# Override sqlalchemy.url with value from settings
config.set_main_option(
    "sqlalchemy.url",
    settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.
    
    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well. By skipping the Engine creation
    we don't even need a DBAPI to be available.
    
    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with connection"""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in async mode"""
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = settings.DATABASE_URL.replace(
        "postgresql://", "postgresql+asyncpg://"
    )
    
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode"""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
