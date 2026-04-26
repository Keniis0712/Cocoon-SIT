"""add group chat debounce settings

Revision ID: 0025_group_chat_agg
Revises: 0024_ext_sender_meta
Create Date: 2026-04-26 15:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = "0025_group_chat_agg"
down_revision: str | None = "0024_ext_sender_meta"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("system_settings") as batch_op:
        batch_op.add_column(
            sa.Column("group_chat_debounce_seconds", sa.Integer(), nullable=False, server_default="2")
        )


def downgrade() -> None:
    with op.batch_alter_table("system_settings") as batch_op:
        batch_op.drop_column("group_chat_debounce_seconds")
