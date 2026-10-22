"""Run Alembic migrations programmatically (used by ``init_db`` and app startup)."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.engine import Engine

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
BASELINE_REVISION = "0001_baseline"

# Tables that existed when Alembic was introduced. A database that has some of
# these but no alembic_version table predates migrations.
BASELINE_TABLES = (
    "users",
    "locations",
    "categories",
    "scores",
    "weights",
    "research",
    "pros_cons",
    "visa_info",
    "profile_responses",
    "ocean_temperature_monthly",
)


def alembic_config(url: str) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    # ConfigParser treats % as interpolation; escape it in URLs.
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return cfg


def adopt_pre_alembic_database(db_engine: Engine) -> bool:
    """Prepare a database created before Alembic so migrations can run on it.

    Patches it with the legacy compat code, creates any missing baseline tables,
    and records it as being at the baseline revision. Returns True if it did so.
    Called from ``migrations/env.py``, so it applies to both ``alembic upgrade``
    on the command line and ``upgrade_database()``.
    """
    existing = set(inspect(db_engine).get_table_names())
    if "alembic_version" in existing or not existing & set(BASELINE_TABLES):
        return False

    from relocation.legacy_compat import run_legacy_compat_migrations

    missing = [name for name in BASELINE_TABLES if name not in existing]
    if missing:
        # The old init_db() ran create_all() on every startup, so a real pre-Alembic
        # database has every baseline table. Building them from today's models would
        # not match the baseline, so refuse rather than guess.
        raise RuntimeError(
            f"Database predates migrations but is missing tables {missing}; "
            "restore it from data/backups/ or start from an empty database."
        )
    run_legacy_compat_migrations(db_engine)

    with db_engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE alembic_version ("
            "version_num VARCHAR(32) NOT NULL, "
            "CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))"
        )
        conn.exec_driver_sql(
            "INSERT INTO alembic_version (version_num) VALUES (?)", (BASELINE_REVISION,)
        )
    return True


def upgrade_database(db_engine: Engine, revision: str = "head") -> None:
    """Upgrade ``db_engine``'s database to ``revision`` (adopting a pre-Alembic DB first)."""
    url = db_engine.url.render_as_string(hide_password=False)
    command.upgrade(alembic_config(url), revision)
