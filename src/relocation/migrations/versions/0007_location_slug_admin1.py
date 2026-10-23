"""Phase 5: location slugs, admin1, region typo fixes.

* ``locations.slug`` -- stable, accent-folded identifier ("rincon-puerto-rico"),
  used for exported markdown filenames. Built from the name plus the
  jurisdiction name in ``countries`` so Puerto Rico places are not "...-usa".
* ``locations.admin1`` -- first-level administrative area from the geocoder
  (state/province). ``region`` stays as a free-text display label.
* Fixes known region typos and stray whitespace.

Revision ID: 0007_location_slug_admin1
Revises: 0006_research_key_facts
"""

import re
import unicodedata
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007_location_slug_admin1"
down_revision: Union[str, Sequence[str], None] = "0006_research_key_facts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

REGION_FIXES = {"Madiera": "Madeira", "Yucután": "Yucatán"}
_EXTRA_FOLDS = str.maketrans({"ß": "ss", "ø": "o", "Ø": "o", "æ": "ae", "Æ": "ae", "ł": "l", "Ł": "l", "đ": "d", "Đ": "d", "ı": "i"})


# Frozen copy of relocation.slugs so this migration never changes behaviour retroactively.
def _slugify(value):
    folded = unicodedata.normalize("NFKD", (value or "").translate(_EXTRA_FOLDS))
    return re.sub(r"[^a-z0-9]+", "-", folded.encode("ascii", "ignore").decode("ascii").lower()).strip("-")


def upgrade() -> None:
    # Plain ADD COLUMN (no table rebuild), so the effective_scores view is untouched.
    op.add_column("locations", sa.Column("slug", sa.String(240), nullable=True))
    op.add_column("locations", sa.Column("admin1", sa.String(100), nullable=True))

    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT l.id, l.name, COALESCE(c.name, l.country) AS country_name, l.region "
            "FROM locations l LEFT JOIN countries c ON c.code = l.country_code ORDER BY l.id"
        )
    ).fetchall()
    used: set[str] = set()
    for row in rows:
        base = "-".join(p for p in (_slugify(row.name), _slugify(row.country_name)) if p) or "location"
        slug = base
        if slug in used and row.region:
            slug = f"{base}-{_slugify(row.region)}"
        suffix = 2
        while slug in used:
            slug = f"{base}-{suffix}"
            suffix += 1
        used.add(slug)
        conn.execute(sa.text("UPDATE locations SET slug = :slug WHERE id = :id"), {"slug": slug, "id": row.id})

    conn.execute(sa.text("UPDATE locations SET region = NULLIF(TRIM(region), '') WHERE region IS NOT NULL"))
    for wrong, right in REGION_FIXES.items():
        conn.execute(sa.text("UPDATE locations SET region = :right WHERE region = :wrong"), {"right": right, "wrong": wrong})

    op.create_index("uq_locations_slug", "locations", ["slug"], unique=True)


def downgrade() -> None:
    conn = op.get_bind()
    # The batch rebuild renames the table, which SQLite refuses while a view references it.
    view_sql = conn.execute(sa.text("SELECT sql FROM sqlite_master WHERE type = 'view' AND name = 'effective_scores'")).scalar()
    if view_sql:
        conn.execute(sa.text("DROP VIEW effective_scores"))
    op.drop_index("uq_locations_slug", table_name="locations")
    with op.batch_alter_table("locations") as batch_op:
        batch_op.drop_column("admin1")
        batch_op.drop_column("slug")
    if view_sql:
        conn.execute(sa.text(view_sql))
