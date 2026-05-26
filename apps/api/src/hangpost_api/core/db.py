"""Database engine, session factory, and the declarative base.

Every ORM model inherits from :class:`Base`. Request handlers depend on
:func:`get_session`, which yields one ``AsyncSession`` per request and
guarantees it is closed afterwards.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from hangpost_api.core.config import get_settings


class Base(DeclarativeBase):
    """Declarative base shared by every domain's ORM models."""


_settings = get_settings()

engine = create_async_engine(
    _settings.database_url,
    echo=_settings.debug,
    pool_pre_ping=True,
)

SessionFactory = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a request-scoped session."""
    async with SessionFactory() as session:
        yield session
