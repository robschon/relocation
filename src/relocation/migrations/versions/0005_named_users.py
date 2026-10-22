"""Phase 3: real names for users.

Adds users.display_name and renames the seeded roles: husband -> partner_a (Partner A),
wife -> partner_b (Partner B). User ids are unchanged, so weights stay attached.

Revision ID: 0005_named_users
Revises: 0004_countries
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_named_users"
down_revision: Union[str, Sequence[str], None] = "0004_countries"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RENAMES = {"husband": ("partner_a", "Partner A"), "wife": ("partner_b", "Partner B")}


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("display_name", sa.String(length=100), nullable=False, server_default=""))
    bind = op.get_bind()
    for old, (new, display) in RENAMES.items():
        bind.exec_driver_sql("UPDATE users SET name = ?, display_name = ? WHERE name = ?", (new, display, old))
    bind.exec_driver_sql("UPDATE users SET display_name = name WHERE display_name = ''")


def downgrade() -> None:
    bind = op.get_bind()
    for old, (new, _display) in RENAMES.items():
        bind.exec_driver_sql("UPDATE users SET name = ? WHERE name = ?", (old, new))
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("display_name")
