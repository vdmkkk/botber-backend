from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from contextlib import asynccontextmanager
from sqlalchemy.pool import NullPool
from app.core.config import settings
import os

DATABASE_URL = (
    f"postgresql+asyncpg://{settings.PG_USER}:{settings.PG_PASSWORD}"
    f"@{settings.PG_HOST}:{settings.PG_PORT}/{settings.PG_DB}"
)

DISABLE_ASYNC_POOL = os.getenv("IN_CELERY", "0") == "1" or os.getenv("DISABLE_ASYNC_DB_POOL", "0") == "1"

engine_kwargs = dict(echo=False, pool_pre_ping=True)
if DISABLE_ASYNC_POOL:
    engine_kwargs["poolclass"] = NullPool

engine = create_async_engine(DATABASE_URL, **engine_kwargs)

AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()

# Dependency for FastAPI routes
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

# NEW: context manager used by background services (billing, pollers, etc.)
@asynccontextmanager
async def async_session():
    async with AsyncSessionLocal() as session:
        yield session
