"""Alembic environment for the relocation database."""

from alembic import context
from sqlalchemy import create_engine, pool

from relocation import models  # noqa: F401 — registers models with Base
from relocation.config import DATABASE_URL
from relocation.database import Base
from relocation.migrate import adopt_pre_alembic_database

config = context.config
target_metadata = Base.metadata


def _url() -> str:
    return config.get_main_option("sqlalchemy.url") or DATABASE_URL


def run_migrations_offline() -> None:
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # A plain engine on purpose: no PRAGMA foreign_keys=ON hook, so SQLite batch
    # table rebuilds (copy -> drop -> rename) don't trip FK constraints. We check
    # FK integrity explicitly once migrations finish.
    connectable = create_engine(_url(), poolclass=pool.NullPool)
    adopt_pre_alembic_database(connectable)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()

        if connection.dialect.name == "sqlite":
            problems = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
            if problems:
                raise RuntimeError(f"Foreign key violations after migration: {problems[:20]}")


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
