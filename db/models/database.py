from __future__ import annotations

from pgvector.asyncpg import register_vector
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine


def build_engine(database_url: str) -> AsyncEngine:
    engine = create_async_engine(database_url, echo=False, pool_pre_ping=True)

    @event.listens_for(engine.sync_engine, "connect")
    def on_connect(dbapi_connection: object, _: object) -> None:
        dbapi_connection.run_async(register_vector)

    return engine


def build_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)

