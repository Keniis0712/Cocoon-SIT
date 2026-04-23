"""add plugin chat group configs

Revision ID: 0011_plugin_chat_group_configs
Revises: 0010_plugin_event_schedule
Create Date: 2026-04-23
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0011_plugin_chat_group_configs"
down_revision = "0010_plugin_event_schedule"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plugin_chat_group_configs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("plugin_id", sa.String(length=64), nullable=False),
        sa.Column("chat_group_id", sa.String(length=64), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("config_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.Column("error_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["plugin_id"], ["plugin_definitions.id"]),
        sa.ForeignKeyConstraint(["chat_group_id"], ["chat_group_rooms.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "plugin_id",
            "chat_group_id",
            name="uq_plugin_chat_group_configs_plugin_id_chat_group_id",
        ),
    )


def downgrade() -> None:
    op.drop_table("plugin_chat_group_configs")
