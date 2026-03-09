from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from relocation.config import DATA_DIR, DATABASE_URL


class Base(DeclarativeBase):
    pass


connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(DATABASE_URL, echo=False, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine)


def get_db():
    """Yield a database session (for FastAPI dependency injection)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables and ensure the data directory exists."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    from relocation import models  # noqa: F401 — registers models with Base

    Base.metadata.create_all(bind=engine)
    _run_sqlite_compat_migrations()


def _run_sqlite_compat_migrations() -> None:
    """Add newly introduced columns to existing SQLite tables."""
    if not DATABASE_URL.startswith("sqlite"):
        return

    def ensure_column(connection, table: str, column: str, ddl: str) -> None:
        rows = connection.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
        existing = {row[1] for row in rows}
        if column not in existing:
            connection.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    def ensure_score_range_allows_zero(connection) -> None:
        row = connection.exec_driver_sql(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='scores'"
        ).fetchone()
        if not row or not row[0]:
            return
        table_sql = str(row[0]).lower()
        if "score >= 0 and score <= 10" in table_sql:
            return

        connection.exec_driver_sql(
            """
            CREATE TABLE scores_new (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                location_id INTEGER NOT NULL,
                category_id INTEGER NOT NULL,
                score INTEGER NOT NULL,
                notes TEXT,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                CONSTRAINT uq_score_loc_cat UNIQUE (location_id, category_id),
                CONSTRAINT ck_score_range CHECK (score >= 0 AND score <= 10),
                FOREIGN KEY(location_id) REFERENCES locations (id),
                FOREIGN KEY(category_id) REFERENCES categories (id)
            )
            """
        )
        connection.exec_driver_sql(
            """
            INSERT INTO scores_new (id, location_id, category_id, score, notes, created_at, updated_at)
            SELECT id, location_id, category_id, score, notes, created_at, updated_at
            FROM scores
            """
        )
        connection.exec_driver_sql("DROP TABLE scores")
        connection.exec_driver_sql("ALTER TABLE scores_new RENAME TO scores")

    with engine.begin() as connection:
        ensure_score_range_allows_zero(connection)

        # locations
        ensure_column(connection, "locations", "latitude", "FLOAT")
        ensure_column(connection, "locations", "longitude", "FLOAT")

        # research
        ensure_column(connection, "research", "source_urls", "TEXT")
        ensure_column(connection, "research", "source_checked_at", "DATE")
        ensure_column(
            connection,
            "research",
            "verification_status",
            "TEXT NOT NULL DEFAULT 'needs_review'",
        )
        ensure_column(connection, "research", "confidence", "FLOAT")

        # visa_info
        ensure_column(connection, "visa_info", "source_urls", "TEXT")
        ensure_column(connection, "visa_info", "source_published_at", "DATE")
        ensure_column(connection, "visa_info", "source_checked_at", "DATE")
        ensure_column(
            connection,
            "visa_info",
            "verification_status",
            "TEXT NOT NULL DEFAULT 'needs_review'",
        )
        ensure_column(connection, "visa_info", "confidence", "FLOAT")
