from __future__ import annotations

import os
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from agentor.durable.models import Base

DEFAULT_SQLITE_URL = "sqlite+aiosqlite:///./celesto.db"


def get_default_database_url() -> str:
    """Resolve database URL with sensible fallbacks."""
    return os.environ.get("CELESTO_DATABASE_URL", DEFAULT_SQLITE_URL)


def create_async_engine_from_url(db_url: Optional[str] = None) -> AsyncEngine:
    """Create an async engine that works for Postgres and SQLite."""
    url = db_url or get_default_database_url()
    engine_kwargs = {"future": True}
    connect_args = {}

    if url.startswith("sqlite"):
        # SQLite dev mode: WAL for better durability and no connection pool
        connect_args = {"check_same_thread": False}
        engine_kwargs["poolclass"] = NullPool

    return create_async_engine(url, connect_args=connect_args, **engine_kwargs)


def build_async_sessionmaker(engine: AsyncEngine):
    """Shared sessionmaker to avoid repeated configuration."""
    return async_sessionmaker(engine, expire_on_commit=False)


async def init_db(engine: AsyncEngine) -> None:
    """Create tables and set SQLite pragmas when needed."""
    async with engine.begin() as conn:
        if conn.dialect.name == "sqlite":
            await conn.execute(text("PRAGMA journal_mode=WAL"))
            await conn.execute(text("PRAGMA synchronous=NORMAL"))

        await conn.run_sync(Base.metadata.create_all)
