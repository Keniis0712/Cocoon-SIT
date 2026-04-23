"""add plugin target bindings

Revision ID: 0009_plugin_target_bindings
Revises: 0008_plugin_user_settings_and_visibility
Create Date: 2026-04-23
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0009_plugin_target_bindings"
down_revision = "0008_plugin_user_settings_and_visibility"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plugin_target_bindings",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("plugin_id", sa.String(length=64), nullable=False),
        sa.Column("scope_type", sa.String(length=32), nullable=False),
        sa.Column("scope_id", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["plugin_id"], ["plugin_definitions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "plugin_id",
            "scope_type",
            "scope_id",
            "target_type",
            "target_id",
            name="uq_plugin_target_bindings_plugin_scope_target",
        ),
    )


def downgrade() -> None:
    op.drop_table("plugin_target_bindings")
