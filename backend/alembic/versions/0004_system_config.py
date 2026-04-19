"""add system settings singleton

Revision ID: 0004_system_config
Revises: 0003_invite_flow
Create Date: 2026-04-19
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0004_system_config"
down_revision = "0003_invite_flow"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "system_settings",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("allow_registration", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("max_chat_turns", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("allowed_model_ids_json", sa.JSON(), nullable=False),
        sa.Column("default_cocoon_temperature", sa.Float(), nullable=False, server_default="0.7"),
        sa.Column("default_max_context_messages", sa.Integer(), nullable=False, server_default="12"),
        sa.Column("default_auto_compaction_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("private_chat_debounce_seconds", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("rollback_retention_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("rollback_cleanup_interval_hours", sa.Integer(), nullable=False, server_default="24"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("system_settings")
