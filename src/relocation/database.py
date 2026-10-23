from datetime import datetime, timezone

from sqlalchemy import DateTime, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.types import TypeDecorator

from relocation.config import DATA_DIR, DATABASE_URL


class UTCDateTime(TypeDecorator):
    """Timestamps are stored as naive UTC (SQLite has no time zones) and read back as aware UTC.

    Aware values are converted to UTC before storing; naive ones are assumed to be UTC
    already. Reading back aware values means the API serialises them with an offset, so
    browsers no longer mistake UTC for local time.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if isinstance(value, datetime) and value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    def process_result_value(self, value, dialect):
        if isinstance(value, datetime):
            return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
        return value


class Base(DeclarativeBase):
    type_annotation_map = {datetime: UTCDateTime()}


def enable_sqlite_foreign_keys(db_engine: Engine) -> Engine:
    """Turn on SQLite foreign-key enforcement for every connection from ``db_engine``.

    SQLite ignores FOREIGN KEY constraints unless ``PRAGMA foreign_keys=ON`` is
    issued on each new connection. Alembic migrations deliberately use their own
    engine without this hook (see ``migrations/env.py``) so table rebuilds work,
    and they run ``PRAGMA foreign_key_check`` afterwards instead.
    """
    if db_engine.dialect.name != "sqlite":
        return db_engine

    @event.listens_for(db_engine, "connect")
    def _set_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return db_engine


connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False
    # Scripts and the API can write at the same time; wait for locks instead of failing.
    connect_args["timeout"] = 15

engine = enable_sqlite_foreign_keys(create_engine(DATABASE_URL, echo=False, connect_args=connect_args))
SessionLocal = sessionmaker(bind=engine)


def get_db():
    """Yield a database session (for FastAPI dependency injection)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Ensure the data directory exists and migrate the database to the latest schema."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    from relocation.migrate import upgrade_database

    upgrade_database(engine)
