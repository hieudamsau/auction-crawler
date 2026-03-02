from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import create_engine

from config.settings import settings


async_engine = create_async_engine(
    settings.db.async_url,
    echo=False,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

sync_engine = create_engine(settings.db.sync_url)


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
