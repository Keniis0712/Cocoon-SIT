"""add plugin user settings and visibility controls

Revision ID: 0008_plugin_user_settings_and_visibility
Revises: 0007_plugin_system
Create Date: 2026-04-23
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0008_plugin_user_settings_and_visibility"
down_revision = "0007_plugin_system"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("plugin_definitions") as batch_op:
        batch_op.add_column(sa.Column("user_config_schema_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")))
        batch_op.add_column(sa.Column("user_default_config_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")))
        batch_op.add_column(sa.Column("settings_validation_function_name", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("is_globally_visible", sa.Boolean(), nullable=False, server_default=sa.text("true")))

    op.create_table(
        "plugin_user_configs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("plugin_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("config_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.Column("error_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["plugin_id"], ["plugin_definitions.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plugin_id", "user_id", name="uq_plugin_user_configs_plugin_id_user_id"),
    )

    op.create_table(
        "plugin_group_visibility",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("plugin_id", sa.String(length=64), nullable=False),
        sa.Column("group_id", sa.String(length=64), nullable=False),
        sa.Column("is_visible", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["plugin_id"], ["plugin_definitions.id"]),
        sa.ForeignKeyConstraint(["group_id"], ["user_groups.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plugin_id", "group_id", name="uq_plugin_group_visibility_plugin_id_group_id"),
    )


def downgrade() -> None:
    op.drop_table("plugin_group_visibility")
    op.drop_table("plugin_user_configs")

    with op.batch_alter_table("plugin_definitions") as batch_op:
        batch_op.drop_column("is_globally_visible")
        batch_op.drop_column("settings_validation_function_name")
        batch_op.drop_column("user_default_config_json")
        batch_op.drop_column("user_config_schema_json")

