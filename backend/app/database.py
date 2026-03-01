from pathlib import Path

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# Resolve database path relative to the backend directory
_backend_dir = Path(__file__).resolve().parent.parent
_db_url = settings.database_url

# If the URL uses a relative path, make it absolute from the backend dir
if _db_url.startswith("sqlite+aiosqlite:///") and not _db_url.startswith(
    "sqlite+aiosqlite:////"
):
    relative_path = _db_url.replace("sqlite+aiosqlite:///", "")
    absolute_path = _backend_dir / relative_path
    absolute_path.parent.mkdir(parents=True, exist_ok=True)
    _db_url = f"sqlite+aiosqlite:///{absolute_path}"

engine = create_async_engine(_db_url, echo=False)


@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragma(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


class Base(DeclarativeBase):
    pass


async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncSession:
    async with async_session_factory() as session:
        yield session


async def _run_migrations():
    """Lightweight schema migrations for columns added after initial release."""
    async with engine.begin() as conn:
        result = await conn.execute(text("PRAGMA table_info(queue_items)"))
        columns = {row[1] for row in result.fetchall()}
        if "generation_backend" not in columns:
            await conn.execute(
                text("ALTER TABLE queue_items ADD COLUMN generation_backend VARCHAR(32)")
            )


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _run_migrations()
