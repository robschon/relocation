"""Phase 1: research runs and provenance; adopt the multi-provider columns.

- New ``research_runs`` table (replaces the in-memory job list, the
  ``location_provider_states`` table and, later, ``locations.full_research_ran_at``).
- ``provider`` on research / scores / pros_cons / visa_info. Databases that already
  have it (from the earlier multi-provider experiment) keep their values; it is
  normalized to VARCHAR(32) NOT NULL DEFAULT 'openai'. Scores stay unique per
  (location, category, provider).
- ``run_id`` on research / scores / pros_cons / visa_info / llm_calls.
- ``research.is_current`` with a partial unique index: one current row per
  (location, category, provider). Older rows stay as history.
- ``scores.method`` (manual / llm / derived) and ``scores.research_id``.
- ``verified_by`` on research / visa_info. Model-asserted "verified" statuses are
  reset to needs_review with verified_by='model-legacy' (Decision 2).

Revision ID: 0003_runs_provenance
Revises: 0002_indexes_llm_calls
"""

from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_runs_provenance"
down_revision: Union[str, Sequence[str], None] = "0002_indexes_llm_calls"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PROVIDER_TABLES = ("research", "pros_cons", "visa_info", "scores")


def _inspector():
    return sa.inspect(op.get_bind())


def _columns(table: str) -> set[str]:
    return {c["name"] for c in _inspector().get_columns(table)}


def _unique_names(table: str) -> set[str]:
    return {u["name"] for u in _inspector().get_unique_constraints(table) if u.get("name")}


def _provider_column() -> sa.Column:
    return sa.Column("provider", sa.String(length=32), nullable=False, server_default="openai")


def _run_fk(batch_op, table: str) -> None:
    batch_op.add_column(sa.Column("run_id", sa.Integer(), nullable=True))
    batch_op.create_foreign_key(f"fk_{table}_run_id", "research_runs", ["run_id"], ["id"], ondelete="SET NULL")


def upgrade() -> None:
    op.create_table(
        "research_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("location_id", sa.Integer(), nullable=True),
        sa.Column("country_code", sa.String(length=2), nullable=True),
        sa.Column("provider", sa.String(length=32), server_default="openai", nullable=False),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("prompt_version", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("step", sa.String(length=200), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("log_tail", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "kind IN ('full', 'category', 'country', 'rescore', 'backfill', 'enrichment')",
            name="ck_research_run_kind",
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'interrupted')",
            name="ck_research_run_status",
        ),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_research_runs_location_started", "research_runs", ["location_id", "started_at"])

    # --- columns -------------------------------------------------------------
    for table in PROVIDER_TABLES:
        has_provider = "provider" in _columns(table)
        uniques = _unique_names(table) if table == "scores" else set()
        with op.batch_alter_table(table, recreate="always") as batch_op:
            if has_provider:
                batch_op.alter_column(
                    "provider",
                    type_=sa.String(length=32),
                    nullable=False,
                    server_default="openai",
                )
            else:
                batch_op.add_column(_provider_column())
            _run_fk(batch_op, table)

            if table == "research":
                batch_op.add_column(sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.text("1")))
                batch_op.add_column(sa.Column("verified_by", sa.String(length=100), nullable=True))
            if table == "visa_info":
                batch_op.add_column(sa.Column("verified_by", sa.String(length=100), nullable=True))
            if table == "scores":
                batch_op.add_column(sa.Column("method", sa.String(length=16), nullable=False, server_default="manual"))
                batch_op.add_column(sa.Column("research_id", sa.Integer(), nullable=True))
                batch_op.create_foreign_key(
                    "fk_scores_research_id", "research", ["research_id"], ["id"], ondelete="SET NULL"
                )
                batch_op.create_check_constraint("ck_score_method", "method IN ('manual', 'llm', 'derived')")
                if "uq_score_loc_cat" in uniques:
                    batch_op.drop_constraint("uq_score_loc_cat", type_="unique")
                if "uq_score_loc_cat_provider" not in uniques:
                    batch_op.create_unique_constraint(
                        "uq_score_loc_cat_provider", ["location_id", "category_id", "provider"]
                    )

    with op.batch_alter_table("llm_calls", recreate="always") as batch_op:
        batch_op.create_foreign_key("fk_llm_calls_run_id", "research_runs", ["run_id"], ["id"], ondelete="SET NULL")

    # --- backfill ------------------------------------------------------------
    bind = op.get_bind()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")

    # One synthetic run owns every row that existed before run tracking.
    first_seen = bind.exec_driver_sql("SELECT min(created_at) FROM research").scalar() or now
    bind.exec_driver_sql(
        "INSERT INTO research_runs (kind, provider, prompt_version, status, step, started_at, finished_at) "
        "VALUES ('backfill', 'openai', 'legacy', 'completed', 'Rows created before run tracking (Phase 1)', ?, ?)",
        (first_seen, now),
    )
    legacy_run_id = bind.exec_driver_sql("SELECT max(id) FROM research_runs").scalar()

    # Past full-research runs we know about become completed 'full' runs.
    bind.exec_driver_sql(
        "INSERT INTO research_runs (kind, location_id, country_code, provider, prompt_version, status, started_at, finished_at) "
        "SELECT 'full', id, country_code, 'openai', 'legacy', 'completed', full_research_ran_at, full_research_ran_at "
        "FROM locations WHERE full_research_ran_at IS NOT NULL"
    )
    if "location_provider_states" in _inspector().get_table_names():
        bind.exec_driver_sql(
            "INSERT INTO research_runs (kind, location_id, provider, prompt_version, status, started_at, finished_at) "
            "SELECT 'full', s.location_id, s.provider, 'legacy', 'completed', s.full_research_ran_at, s.full_research_ran_at "
            "FROM location_provider_states s "
            "WHERE s.full_research_ran_at IS NOT NULL AND NOT EXISTS ("
            "  SELECT 1 FROM research_runs r WHERE r.kind = 'full' AND r.location_id = s.location_id "
            "  AND r.provider = s.provider AND r.finished_at = s.full_research_ran_at)"
        )
        op.drop_table("location_provider_states")

    for table in PROVIDER_TABLES:
        bind.exec_driver_sql(f"UPDATE {table} SET run_id = ? WHERE run_id IS NULL", (legacy_run_id,))

    # Newest row per (location, category, provider) is current; the rest are history.
    bind.exec_driver_sql(
        "UPDATE research SET is_current = CASE WHEN id IN ("
        "  SELECT max(id) FROM research GROUP BY location_id, category_id, provider"
        ") THEN 1 ELSE 0 END"
    )

    # Decision 2: only people (or explicit rules) mark things verified.
    bind.exec_driver_sql(
        "UPDATE research SET verified_by = 'model-legacy', verification_status = 'needs_review' "
        "WHERE verification_status = 'verified'"
    )
    bind.exec_driver_sql(
        "UPDATE visa_info SET verified_by = 'rule:us-citizen' "
        "WHERE verification_status = 'verified' AND visa_type LIKE 'No visa required (U.S. citizen%'"
    )
    bind.exec_driver_sql(
        "UPDATE visa_info SET verified_by = 'model-legacy', verification_status = 'needs_review' "
        "WHERE verification_status = 'verified' AND verified_by IS NULL"
    )

    # Every pre-existing score came from the LLM pipeline (including swim/beach; see the audit).
    bind.exec_driver_sql(
        "UPDATE scores SET method = 'llm', research_id = ("
        "  SELECT r.id FROM research r WHERE r.location_id = scores.location_id "
        "  AND r.category_id = scores.category_id AND r.provider = scores.provider AND r.is_current = 1)"
    )

    op.create_index(
        "uq_research_current",
        "research",
        ["location_id", "category_id", "provider"],
        unique=True,
        sqlite_where=sa.text("is_current = 1"),
    )


def downgrade() -> None:
    # provider columns are kept: databases that predate this revision already had them.
    op.drop_index("uq_research_current", table_name="research")
    with op.batch_alter_table("llm_calls", recreate="always") as batch_op:
        batch_op.drop_constraint("fk_llm_calls_run_id", type_="foreignkey")
    with op.batch_alter_table("scores", recreate="always") as batch_op:
        batch_op.drop_constraint("fk_scores_research_id", type_="foreignkey")
        batch_op.drop_constraint("ck_score_method", type_="check")
        batch_op.drop_column("research_id")
        batch_op.drop_column("method")
    for table in PROVIDER_TABLES:
        with op.batch_alter_table(table, recreate="always") as batch_op:
            batch_op.drop_constraint(f"fk_{table}_run_id", type_="foreignkey")
            batch_op.drop_column("run_id")
            if table == "research":
                batch_op.drop_column("is_current")
            if table in ("research", "visa_info"):
                batch_op.drop_column("verified_by")
    op.drop_index("ix_research_runs_location_started", table_name="research_runs")
    op.drop_table("research_runs")
