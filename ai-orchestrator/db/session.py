"""
SQLAlchemy async engine + session factory.

get_session() is an async context manager for use inside FastAPI endpoints.
init_db() runs Alembic migrations programmatically on startup so the schema
is always up to date without a separate migration step in production.
"""
import structlog
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import get_settings

logger = structlog.get_logger()

_engine = None
_session_factory: async_sessionmaker | None = None


def _get_engine():
    global _engine
    if _engine is None:
        url = get_settings().database_url
        _engine = create_async_engine(
            url,
            pool_size=5,
            max_overflow=10,
            echo=False,
        )
    return _engine


def _get_factory() -> async_sessionmaker:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=_get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


@asynccontextmanager
async def get_session() -> AsyncSession:
    """Async context manager yielding a transactional session."""
    async with _get_factory()() as session:
        async with session.begin():
            yield session


async def init_db() -> None:
    """Run Alembic upgrade to head on startup."""
    import asyncio
    from alembic import command
    from alembic.config import Config
    from pathlib import Path

    cfg_path = Path(__file__).parent / "migrations" / "alembic.ini"
    alembic_cfg = Config(str(cfg_path))

    logger.info("Running Alembic migrations", config=str(cfg_path))

    # Alembic's command.upgrade is synchronous — run in threadpool
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, lambda: command.upgrade(alembic_cfg, "head"))
    logger.info("Alembic migrations complete")


async def close_db() -> None:
    """Dispose the async engine (call on app shutdown)."""
    global _engine
    if _engine:
        await _engine.dispose()
        _engine = None
