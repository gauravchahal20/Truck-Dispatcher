import os
from pathlib import Path
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from .config import settings, config, PROJECT_ROOT

# SQLAlchemy Declarative Base
Base = declarative_base()

# Determine DB URL (environment variable takes precedence for test isolation)
db_url = os.environ.get("DATABASE_URL") or settings.database_url or config.raw_yaml.get("system", {}).get("database_url", "sqlite+aiosqlite:///./data/trucklead.db")

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
    """Initializes database schema, tables, and applies schema migrations."""
    # Import all models to ensure they are registered with Base
    from .. import models  # noqa
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        def _migrate_sqlite_columns(sync_conn):
            from sqlalchemy import text
            company_new_cols = [
                ("phone_e164", "VARCHAR(50)"),
                ("phone_display", "VARCHAR(50)"),
                ("phone_line_type", "VARCHAR(50)"),
                ("phone_carrier_name", "VARCHAR(100)"),
                ("phone_country_code", "VARCHAR(10) DEFAULT 'US'"),
                ("phone_verification_status", "VARCHAR(50) DEFAULT 'UNKNOWN'"),
                ("phone_verified_at", "DATETIME"),
                ("phone_verification_provider", "VARCHAR(50)"),
                ("phone_raw_status", "VARCHAR(100)"),
                ("phone_cost", "FLOAT DEFAULT 0.0"),
                ("call_guidance", "VARCHAR(100)"),
                ("dnc_status", "VARCHAR(100) DEFAULT 'DNC not checked'"),
                ("local_timezone", "VARCHAR(50)"),
                ("call_window_local", "VARCHAR(100)"),
                ("call_window_ist", "VARCHAR(100)"),
                ("email_verification_status", "VARCHAR(50) DEFAULT 'UNKNOWN'"),
                ("email_mx_valid", "BOOLEAN"),
                ("email_is_disposable", "BOOLEAN DEFAULT 0"),
                ("email_role_tier", "VARCHAR(50)"),
                ("email_verified_at", "DATETIME"),
                ("email_verification_provider", "VARCHAR(50)"),
                ("fit_score", "FLOAT DEFAULT 0.0"),
                ("intent_score", "FLOAT DEFAULT 0.0"),
                ("scoring_version", "VARCHAR(20) DEFAULT '2.0'"),
            ]
            contact_new_cols = [
                ("phone_e164", "VARCHAR(50)"),
                ("phone_display", "VARCHAR(50)"),
                ("phone_line_type", "VARCHAR(50)"),
                ("phone_carrier_name", "VARCHAR(100)"),
                ("phone_verification_status", "VARCHAR(50) DEFAULT 'UNKNOWN'"),
                ("phone_verified_at", "DATETIME"),
                ("phone_verification_provider", "VARCHAR(50)"),
                ("phone_raw_status", "VARCHAR(100)"),
                ("phone_cost", "FLOAT DEFAULT 0.0"),
                ("dnc_status", "VARCHAR(100) DEFAULT 'DNC not checked'"),
                ("email_verification_status", "VARCHAR(50) DEFAULT 'UNKNOWN'"),
                ("email_mx_valid", "BOOLEAN"),
                ("email_is_disposable", "BOOLEAN DEFAULT 0"),
                ("email_role_tier", "VARCHAR(50)"),
                ("email_verified_at", "DATETIME"),
                ("email_verification_provider", "VARCHAR(50)"),
            ]
            lead_score_new_cols = [
                ("fit_score", "FLOAT DEFAULT 0.0"),
                ("intent_score", "FLOAT DEFAULT 0.0"),
                ("scoring_version", "VARCHAR(20) DEFAULT '2.0'"),
            ]
            intent_signal_new_cols = [
                ("strength", "FLOAT DEFAULT 1.0"),
                ("observed_at", "DATETIME"),
                ("half_life_days", "FLOAT DEFAULT 60.0"),
                ("evidence", "JSON"),
                ("is_sensitive", "BOOLEAN DEFAULT 0"),
            ]
            try:
                res_comp = sync_conn.execute(text("PRAGMA table_info(companies)")).fetchall()
                existing_comp = {row[1] for row in res_comp}
                for col_name, col_type in company_new_cols:
                    if col_name not in existing_comp:
                        sync_conn.execute(text(f"ALTER TABLE companies ADD COLUMN {col_name} {col_type}"))

                res_cont = sync_conn.execute(text("PRAGMA table_info(contacts)")).fetchall()
                existing_cont = {row[1] for row in res_cont}
                for col_name, col_type in contact_new_cols:
                    if col_name not in existing_cont:
                        sync_conn.execute(text(f"ALTER TABLE contacts ADD COLUMN {col_name} {col_type}"))

                res_ls = sync_conn.execute(text("PRAGMA table_info(lead_scores)")).fetchall()
                existing_ls = {row[1] for row in res_ls}
                for col_name, col_type in lead_score_new_cols:
                    if col_name not in existing_ls:
                        sync_conn.execute(text(f"ALTER TABLE lead_scores ADD COLUMN {col_name} {col_type}"))

                res_sig = sync_conn.execute(text("PRAGMA table_info(intent_signals)")).fetchall()
                existing_sig = {row[1] for row in res_sig}
                for col_name, col_type in intent_signal_new_cols:
                    if col_name not in existing_sig:
                        sync_conn.execute(text(f"ALTER TABLE intent_signals ADD COLUMN {col_name} {col_type}"))
            except Exception as e:
                print(f"Warning: SQLite migration error: {e}")

        await conn.run_sync(_migrate_sqlite_columns)



