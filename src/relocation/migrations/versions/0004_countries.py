"""Phase 2: countries, category flags, country-level visa research and scores.

- ``countries`` (ISO alpha-2, with parent jurisdictions: PR -> US, GP -> FR, CW -> NL).
  locations.country_code and visa_info.country_code become NOT NULL foreign keys.
  Missing codes are filled (Cuba, India, Sri Lanka, Madagascar, Slovenia).
- Puerto Rico becomes its own jurisdiction (Decision 1): Luquillo, Rincón and
  Esperanza move from US to PR; the generic "US Territories" visa rows are removed.
  Duplicate visa rows (same country, type, provider) are collapsed to the newest.
- ``categories`` gain key / scope / kind / needs_web / requires_citation /
  refresh_after_days. Visa/residency is scope=country; tax stays per location
  because it varies by state/region (US, Spain).
- research rows can belong to a country (location_id NULL, country_code set).
  For visa, the newest current location row per country becomes the country's
  current row; the others become history.
- ``country_scores``: visa score per country = median of its locations' scores
  (rounded half up). Per-location visa scores are removed.
- ``effective_scores`` view: location scores plus country scores expanded to
  every location in the country, for raw-SQL readers.

Downgrade is not supported: restore data/backups/ instead.

Revision ID: 0004_countries
Revises: 0003_runs_provenance
"""

import math
from collections import defaultdict
from statistics import median
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_countries"
down_revision: Union[str, Sequence[str], None] = "0003_runs_provenance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MISSING_CODES = {
    "Cuba": "CU",
    "India": "IN",
    "Sri Lanka": "LK",
    "Madagascar": "MG",
    "Slovenia": "SI",
}
PARENTS = {"PR": "US", "GP": "FR", "CW": "NL"}
EXTRA_COUNTRIES = {"NL": "Netherlands"}  # parent of Curaçao

# name -> (key, scope, kind, needs_web, requires_citation, refresh_after_days)
CATEGORY_FLAGS = {
    "Cost of living / housing": ("cost_of_living", "location", "researched", 1, 0, 365),
    "Climate / weather": ("climate", "location", "researched", 0, 0, None),
    "Healthcare quality & access": ("healthcare", "location", "researched", 1, 0, 365),
    "Visa / residency feasibility": ("visa", "country", "researched", 1, 1, 90),
    "Tax implications": ("tax", "location", "researched", 1, 1, 90),
    "Safety / stability / values": ("safety_values", "location", "researched", 0, 0, 365),
    "Language & community": ("language_community", "location", "researched", 0, 0, None),
    "Walkability / public transit": ("walkability", "location", "researched", 0, 0, None),
    "Cultural amenities / lifestyle": ("culture", "location", "researched", 0, 0, None),
    "Travel connectivity & proximity to family/friends": ("travel_connectivity", "location", "researched", 1, 0, 365),
    "Food scene": ("food", "location", "researched", 0, 0, None),
    "Natural beauty / outdoor recreation": ("nature", "location", "researched", 0, 0, None),
    "Environmental quality & climate risk": ("environment_climate_risk", "location", "researched", 0, 0, None),
    "Year-round swimming viability": ("swimming", "location", "derived", 0, 0, None),
    "Beach accessibility": ("beach_access", "location", "derived", 0, 0, None),
}

EFFECTIVE_SCORES_VIEW = """
CREATE VIEW effective_scores AS
SELECT
    s.id AS score_id, NULL AS country_score_id, s.location_id, s.category_id, s.provider,
    s.score, s.notes, s.method, s.research_id, s.run_id, 'location' AS scope, l.country_code,
    s.created_at, s.updated_at
FROM scores s
JOIN categories c ON c.id = s.category_id AND c.scope = 'location'
JOIN locations l ON l.id = s.location_id
UNION ALL
SELECT
    NULL, cs.id, l.id, cs.category_id, cs.provider,
    cs.score, cs.notes, cs.method, cs.research_id, cs.run_id, 'country', cs.country_code,
    cs.created_at, cs.updated_at
FROM country_scores cs
JOIN categories c ON c.id = cs.category_id AND c.scope = 'country'
JOIN locations l ON l.country_code = cs.country_code
"""


def _slug(value: str) -> str:
    return "_".join("".join(ch if ch.isalnum() else " " for ch in value.lower()).split())[:50]


def upgrade() -> None:
    bind = op.get_bind()
    sql = bind.exec_driver_sql

    # --- country codes and Puerto Rico --------------------------------------
    for name, code in MISSING_CODES.items():
        sql("UPDATE locations SET country_code = ? WHERE country = ? AND country_code IS NULL", (code, name))
        sql("UPDATE visa_info SET country_code = ? WHERE country = ? AND country_code IS NULL", (code, name))
    sql(
        "UPDATE locations SET country = 'Puerto Rico', country_code = 'PR' "
        "WHERE country_code = 'US' AND region = 'Puerto Rico'"
    )
    sql("DELETE FROM visa_info WHERE country = 'US Territories' AND country_code IS NULL")
    sql(
        "DELETE FROM visa_info WHERE id NOT IN ("
        "  SELECT max(id) FROM visa_info GROUP BY country_code, visa_type, provider)"
    )
    for table in ("locations", "visa_info"):
        missing = sql(f"SELECT DISTINCT country FROM {table} WHERE country_code IS NULL").fetchall()
        if missing:
            raise RuntimeError(f"{table} rows without a country code: {[m[0] for m in missing]}")

    op.create_table(
        "countries",
        sa.Column("code", sa.String(length=2), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("parent_code", sa.String(length=2), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["parent_code"], ["countries.code"]),
        sa.PrimaryKeyConstraint("code"),
    )
    names: dict[str, str] = dict(EXTRA_COUNTRIES)
    for code, name in sql(
        "SELECT country_code, min(country) FROM ("
        "  SELECT country_code, country FROM locations UNION SELECT country_code, country FROM visa_info"
        ") GROUP BY country_code"
    ).fetchall():
        names[code] = name
    for code in PARENTS.values():
        names.setdefault(code, {"US": "United States", "FR": "France", "NL": "Netherlands"}[code])
    now = sql("SELECT strftime('%Y-%m-%d %H:%M:%f', 'now')").scalar()
    for code in sorted(names, key=lambda c: c in PARENTS):  # parents first
        sql(
            "INSERT INTO countries (code, name, parent_code, created_at) VALUES (?, ?, ?, ?)",
            (code, names[code], PARENTS.get(code), now),
        )

    with op.batch_alter_table("locations", recreate="always") as batch_op:
        batch_op.alter_column("country_code", existing_type=sa.String(length=2), type_=sa.String(length=2), nullable=False)
        batch_op.create_foreign_key("fk_locations_country_code", "countries", ["country_code"], ["code"])
    with op.batch_alter_table("visa_info", recreate="always") as batch_op:
        batch_op.alter_column("country_code", existing_type=sa.String(length=2), type_=sa.String(length=2), nullable=False)
        batch_op.create_foreign_key("fk_visa_info_country_code", "countries", ["country_code"], ["code"])

    # --- category flags ------------------------------------------------------
    with op.batch_alter_table("categories", recreate="always") as batch_op:
        batch_op.add_column(sa.Column("key", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("scope", sa.String(length=16), nullable=False, server_default="location"))
        batch_op.add_column(sa.Column("kind", sa.String(length=16), nullable=False, server_default="researched"))
        batch_op.add_column(sa.Column("needs_web", sa.Boolean(), nullable=False, server_default=sa.text("0")))
        batch_op.add_column(sa.Column("requires_citation", sa.Boolean(), nullable=False, server_default=sa.text("0")))
        batch_op.add_column(sa.Column("refresh_after_days", sa.Integer(), nullable=True))
        batch_op.create_check_constraint("ck_category_scope", "scope IN ('location', 'country')")
        batch_op.create_check_constraint("ck_category_kind", "kind IN ('researched', 'derived')")
    for cat_id, name in sql("SELECT id, name FROM categories").fetchall():
        key, scope, kind, web, cite, refresh = CATEGORY_FLAGS.get(name, (_slug(name), "location", "researched", 0, 0, None))
        sql(
            "UPDATE categories SET key = ?, scope = ?, kind = ?, needs_web = ?, requires_citation = ?, "
            "refresh_after_days = ? WHERE id = ?",
            (key, scope, kind, web, cite, refresh, cat_id),
        )
    with op.batch_alter_table("categories", recreate="always") as batch_op:
        batch_op.alter_column("key", existing_type=sa.String(length=50), nullable=False)
        batch_op.create_unique_constraint("uq_categories_key", ["key"])

    # --- research subjects -----------------------------------------------------
    # Partial indexes are dropped around the table rebuild and recreated explicitly.
    op.drop_index("uq_research_current", table_name="research")
    with op.batch_alter_table("research", recreate="always") as batch_op:
        batch_op.alter_column("location_id", existing_type=sa.Integer(), nullable=True)
        batch_op.add_column(sa.Column("country_code", sa.String(length=2), nullable=True))
        batch_op.create_foreign_key("fk_research_country_code", "countries", ["country_code"], ["code"])
        batch_op.create_check_constraint("ck_research_subject", "(location_id IS NULL) != (country_code IS NULL)")

    op.create_table(
        "country_scores",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("country_code", sa.String(length=2), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=32), server_default="openai", nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("method", sa.String(length=16), server_default="manual", nullable=False),
        sa.Column("research_id", sa.Integer(), nullable=True),
        sa.Column("run_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("score >= 0 AND score <= 10", name="ck_country_score_range"),
        sa.CheckConstraint("method IN ('manual', 'llm', 'derived')", name="ck_country_score_method"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"]),
        sa.ForeignKeyConstraint(["country_code"], ["countries.code"]),
        sa.ForeignKeyConstraint(["research_id"], ["research.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["run_id"], ["research_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("country_code", "category_id", "provider", name="uq_country_score_country_cat_provider"),
    )

    # --- move country-scope evidence and scores --------------------------------
    for (category_id,) in sql("SELECT id FROM categories WHERE scope = 'country'").fetchall():
        chosen: dict[tuple[str, str], tuple[int, int]] = {}  # (country, provider) -> (research_id, location_id)
        for research_id, location_id, country_code, provider in sql(
            "SELECT r.id, r.location_id, l.country_code, r.provider FROM research r "
            "JOIN locations l ON l.id = r.location_id WHERE r.category_id = ? AND r.is_current = 1",
            (category_id,),
        ).fetchall():
            slot = (country_code, provider)
            if slot not in chosen or research_id > chosen[slot][0]:
                chosen[slot] = (research_id, location_id)
        sql("UPDATE research SET is_current = 0 WHERE category_id = ? AND location_id IS NOT NULL", (category_id,))
        for (country_code, _provider), (research_id, _loc) in chosen.items():
            sql(
                "UPDATE research SET location_id = NULL, country_code = ?, is_current = 1 WHERE id = ?",
                (country_code, research_id),
            )

        grouped: dict[tuple[str, str], list] = defaultdict(list)
        for row in sql(
            "SELECT l.country_code, s.provider, s.score, s.notes, s.method, s.run_id, s.location_id, "
            "s.created_at, s.updated_at FROM scores s JOIN locations l ON l.id = s.location_id "
            "WHERE s.category_id = ?",
            (category_id,),
        ).fetchall():
            grouped[(row[0], row[1])].append(row)
        for (country_code, provider), rows in grouped.items():
            value = int(math.floor(median(r[2] for r in rows) + 0.5))
            research_id, source_location = chosen.get((country_code, provider), (None, None))
            source = next((r for r in rows if r[6] == source_location), rows[0])
            method = "llm" if all(r[4] == "llm" for r in rows) else "manual"
            sql(
                "INSERT INTO country_scores (country_code, category_id, provider, score, notes, method, "
                "research_id, run_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (country_code, category_id, provider, value, source[3], method, research_id, source[5],
                 min(r[7] for r in rows), max(r[8] for r in rows)),
            )
        sql("DELETE FROM scores WHERE category_id = ?", (category_id,))

    op.create_index("ix_research_country_category", "research", ["country_code", "category_id"])
    op.create_index(
        "uq_research_current",
        "research",
        ["location_id", "category_id", "provider"],
        unique=True,
        sqlite_where=sa.text("is_current = 1"),
    )
    op.create_index(
        "uq_research_country_current",
        "research",
        ["country_code", "category_id", "provider"],
        unique=True,
        sqlite_where=sa.text("is_current = 1 AND location_id IS NULL"),
    )
    sql(EFFECTIVE_SCORES_VIEW)


def downgrade() -> None:
    raise NotImplementedError(
        "0004_countries moves visa research/scores to countries and cannot be reversed in place; "
        "restore a backup from data/backups/ instead."
    )
