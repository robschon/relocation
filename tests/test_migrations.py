"""Alembic migrations: fresh databases, pre-Alembic databases, and model drift."""

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from relocation import models
from relocation.database import Base, enable_sqlite_foreign_keys
from alembic import command

from relocation.migrate import alembic_config, upgrade_database


def _head_revision(engine) -> str:
    with engine.connect() as conn:
        return conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()


@pytest.fixture
def file_engine(tmp_path):
    engine = enable_sqlite_foreign_keys(create_engine(f"sqlite:///{tmp_path / 'test.db'}"))
    yield engine
    engine.dispose()


def test_fresh_database_matches_models(file_engine):
    upgrade_database(file_engine)

    assert _head_revision(file_engine) == "0006_research_key_facts"
    with file_engine.connect() as conn:
        diffs = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diffs == [], f"Models and migrations disagree; write a migration: {diffs}"


def test_upgrade_is_idempotent(file_engine):
    upgrade_database(file_engine)
    upgrade_database(file_engine)
    assert _head_revision(file_engine) == "0006_research_key_facts"


def _make_pre_alembic_database(engine) -> None:
    """Build the schema as it was when Alembic arrived, without an alembic_version table."""
    upgrade_database(engine, "0001_baseline")
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE alembic_version"))


def test_pre_alembic_database_is_stamped_and_upgraded(file_engine):
    _make_pre_alembic_database(file_engine)
    with file_engine.begin() as conn:
        conn.execute(text("INSERT INTO categories (name, sort_order, created_at) VALUES ('X', 1, '2026-01-01')"))

    upgrade_database(file_engine)

    tables = set(inspect(file_engine).get_table_names())
    assert {"alembic_version", "llm_calls"} <= tables
    assert _head_revision(file_engine) == "0006_research_key_facts"
    with file_engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM categories")).scalar_one() == 1


def test_alembic_cli_path_adopts_pre_alembic_database(file_engine):
    """`alembic upgrade head` (not just app startup) must handle a pre-Alembic DB."""
    _make_pre_alembic_database(file_engine)
    command.upgrade(alembic_config(file_engine.url.render_as_string(hide_password=False)), "head")
    assert _head_revision(file_engine) == "0006_research_key_facts"
    assert "llm_calls" in inspect(file_engine).get_table_names()


def test_pre_alembic_database_missing_tables_is_refused(file_engine):
    _make_pre_alembic_database(file_engine)
    with file_engine.begin() as conn:
        conn.execute(text("DROP TABLE profile_responses"))
    with pytest.raises(RuntimeError, match="missing tables"):
        upgrade_database(file_engine)


def test_foreign_keys_are_enforced(db_session):
    db_session.add(models.Score(location_id=999_999, category_id=1, score=5))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
