"""remove plugin dispatch dedupe key

Revision ID: 0012_remove_plugin_dedupe
Revises: 0011_plugin_group_cfgs
Create Date: 2026-04-23
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0012_remove_plugin_dedupe"
down_revision = "0011_plugin_group_cfgs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("plugin_dispatch_records") as batch_op:
        batch_op.drop_constraint("uq_plugin_dispatch_records_dedupe", type_="unique")
        batch_op.drop_column("dedupe_key")


def downgrade() -> None:
    with op.batch_alter_table("plugin_dispatch_records") as batch_op:
        batch_op.add_column(sa.Column("dedupe_key", sa.String(length=255), nullable=True))
        batch_op.create_unique_constraint(
            "uq_plugin_dispatch_records_dedupe",
            ["plugin_id", "event_name", "dedupe_key"],
        )
