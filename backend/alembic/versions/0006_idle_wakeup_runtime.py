"""add wakeup cancellation tracking for structured idle runtime

Revision ID: 0006_idle_wakeup_runtime
Revises: 0005_chat_groups
Create Date: 2026-04-19
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0006_idle_wakeup_runtime"
down_revision = "0005_chat_groups"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("wakeup_tasks") as batch_op:
        batch_op.add_column(sa.Column("cancelled_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("superseded_by_task_id", sa.String(length=64), nullable=True))
        batch_op.create_foreign_key(
            "fk_wakeup_tasks_superseded_by_task_id_wakeup_tasks",
            "wakeup_tasks",
            ["superseded_by_task_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("wakeup_tasks") as batch_op:
        batch_op.drop_constraint("fk_wakeup_tasks_superseded_by_task_id_wakeup_tasks", type_="foreignkey")
        batch_op.drop_column("superseded_by_task_id")
        batch_op.drop_column("cancelled_at")
