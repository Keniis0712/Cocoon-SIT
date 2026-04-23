"""add plugin event schedule settings

Revision ID: 0010_plugin_schedule
Revises: 0009_plugin_targets
Create Date: 2026-04-23
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0010_plugin_schedule"
down_revision = "0009_plugin_targets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("plugin_event_configs") as batch_op:
        batch_op.add_column(sa.Column("schedule_mode", sa.String(length=32), nullable=False, server_default="manual"))
        batch_op.add_column(sa.Column("schedule_interval_seconds", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("schedule_cron", sa.String(length=255), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("plugin_event_configs") as batch_op:
        batch_op.drop_column("schedule_cron")
        batch_op.drop_column("schedule_interval_seconds")
        batch_op.drop_column("schedule_mode")
