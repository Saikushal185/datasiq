from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from backend.app.core.config import get_alembic_database_url as _get_alembic_database_url
from backend.app.core.config import get_database_url


@lru_cache
def get_engine() -> AsyncEngine:
    return create_async_engine(get_database_url(), future=True, pool_pre_ping=True)


@lru_cache
def get_session_maker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(bind=get_engine(), class_=AsyncSession, expire_on_commit=False)


def get_alembic_database_url() -> str:
    return _get_alembic_database_url()


engine = get_engine()
AsyncSessionLocal = get_session_maker()


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session
