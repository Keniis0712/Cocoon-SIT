"""add per-user permission overrides

Revision ID: 0017_user_permission_overrides
Revises: 0016_runtime_tag_system
Create Date: 2026-04-25 14:20:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0017_user_permission_overrides"
down_revision: str | None = "0016_runtime_tag_system"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column("permissions_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'"))
        )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("permissions_json")
