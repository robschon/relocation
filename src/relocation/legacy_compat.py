"""Schema patches for databases created before Alembic was introduced (Phase 0)."""

from sqlalchemy.engine import Engine

from relocation.countries import normalize_country_fields


def run_legacy_compat_migrations(engine: Engine) -> None:
    """Bring a pre-Alembic SQLite database up to the 0001_baseline shape.

    This is the column-patching code that used to run in ``init_db()`` on every
    startup. It now runs at most once per database: only when the database has
    tables but no ``alembic_version`` table, right before it is stamped at the
    baseline revision. Do not add new schema changes here; write an Alembic
    migration instead.
    """
    if engine.dialect.name != "sqlite":
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

    def backfill_country_metadata(connection, table: str) -> None:
        rows = connection.exec_driver_sql(
            f"SELECT id, country, country_code FROM {table}"
        ).fetchall()
        for row in rows:
            record_id, country, country_code = row
            normalized_country, normalized_code = normalize_country_fields(
                country=country,
                country_code=country_code,
            )
            if normalized_country != country or normalized_code != country_code:
                connection.exec_driver_sql(
                    f"UPDATE {table} SET country = ?, country_code = ? WHERE id = ?",
                    (normalized_country, normalized_code, record_id),
                )

    with engine.begin() as connection:
        ensure_score_range_allows_zero(connection)

        # locations
        ensure_column(connection, "locations", "country_code", "TEXT")
        ensure_column(connection, "locations", "latitude", "FLOAT")
        ensure_column(connection, "locations", "longitude", "FLOAT")
        ensure_column(connection, "locations", "full_research_ran_at", "DATETIME")
        backfill_country_metadata(connection, "locations")

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
        ensure_column(connection, "visa_info", "country_code", "TEXT")
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
        backfill_country_metadata(connection, "visa_info")
