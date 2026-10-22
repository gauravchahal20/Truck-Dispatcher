from pathlib import Path
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from .config import settings, config, PROJECT_ROOT

# SQLAlchemy Declarative Base
Base = declarative_base()

# Determine DB URL
db_url = settings.database_url or config.raw_yaml.get("system", {}).get("database_url", "sqlite+aiosqlite:///./trucklead.db")

# Normalize relative SQLite paths to PROJECT_ROOT
if "sqlite" in db_url:
    prefix = "sqlite+aiosqlite:///"
    if db_url.startswith(prefix):
        raw_path = db_url[len(prefix):]
        # If it's relative (not Windows drive letter F: and not absolute root path)
        if not (len(raw_path) > 1 and raw_path[1] == ":") and not raw_path.startswith("/") and not raw_path.startswith("\\"):
            clean_rel = raw_path.lstrip("./").lstrip(".\\")
            resolved_db = (PROJECT_ROOT / clean_rel).resolve()
            db_url = f"{prefix}{resolved_db.as_posix()}"

from sqlalchemy import event

# Create Async Engine
engine_kwargs = {"echo": False, "future": True}
if "sqlite" in db_url:
    engine_kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30.0}

async_engine = create_async_engine(db_url, **engine_kwargs)

if "sqlite" in db_url:
    @event.listens_for(async_engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        try:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=15000")
            cursor.close()
        except Exception:
            pass


# Async Session Factory
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency injection for database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def init_db():
    """Initializes database schema and tables."""
    # Import all models to ensure they are registered with Base
    from .. import models  # noqa
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
