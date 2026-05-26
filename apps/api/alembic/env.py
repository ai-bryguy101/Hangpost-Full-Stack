"""Alembic environment — async engine, settings-driven URL.

The URL comes from ``hangpost_api.core.config`` so migrations use the same
configuration as the app. ``hangpost_api.models`` is imported to register
every table on ``Base.metadata`` for autogenerate.
"""

import asyncio

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

import hangpost_api.models  # noqa: F401  (registers all models on Base.metadata)
from hangpost_api.core.config import get_settings
from hangpost_api.core.db import Base

config = context.config
target_metadata = Base.metadata
DATABASE_URL = get_settings().database_url


def run_migrations_offline() -> None:
    """Emit SQL to stdout without a live connection (``alembic --sql``)."""
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations against a live async connection."""
    engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
    async with engine.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
