"""add external sender metadata to messages

Revision ID: 0024_ext_sender_meta
Revises: 0023_plugin_scope_error_split
Create Date: 2026-04-26 12:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = "0024_ext_sender_meta"
down_revision: str | None = "0023_plugin_scope_error_split"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("messages") as batch_op:
        batch_op.add_column(sa.Column("external_sender_id", sa.String(length=255), nullable=True))
        batch_op.add_column(
            sa.Column("external_sender_display_name", sa.String(length=255), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("messages") as batch_op:
        batch_op.drop_column("external_sender_display_name")
        batch_op.drop_column("external_sender_id")
