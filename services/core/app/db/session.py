"""Async SQLAlchemy engine/session. DRAFT: db/models is Person B's territory
(work-distribution.md §2.2) but engine setup is needed by every repo, A's
included, so this is written now against DATABASE_URL and reviewed/merged
with whatever session setup B builds alongside app/db/models/**."""

import os
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://gh:gh@localhost:5432/goldenhour")

engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@asynccontextmanager
async def get_session():
    async with SessionLocal() as session:
        yield session
