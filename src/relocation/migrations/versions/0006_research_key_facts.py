"""Phase 4: structured key facts on research rows.

v2 research stores a short summary in ``content`` plus 5-10 ``key_facts``
({fact, value, source_url}). Older rows have NULL key_facts.

Revision ID: 0006_research_key_facts
Revises: 0005_named_users
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_research_key_facts"
down_revision: Union[str, Sequence[str], None] = "0005_named_users"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Plain ADD COLUMN (no table rebuild), so the effective_scores view and partial indexes are untouched.
    op.add_column("research", sa.Column("key_facts", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("research") as batch_op:
        batch_op.drop_column("key_facts")
