"""Async SQLAlchemy engine + session factory.

The app uses async SQLAlchemy across the API hot path so a slow query
doesn't block the event loop and starve other in-flight requests.
"""
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    """Single declarative base for all ORM models."""


engine = create_async_engine(
    settings.database_url,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,  # detect dropped connections after DB restart
    echo=False,
)

SessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,  # don't reissue SELECT after commit
    class_=AsyncSession,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency. Wrap each request in a session that auto-closes."""
    async with SessionLocal() as session:
        yield session
