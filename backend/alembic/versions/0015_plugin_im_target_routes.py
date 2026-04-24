"""add plugin im target routes

Revision ID: 0015_plugin_im_target_routes
Revises: 0014_user_im_bind_tokens
Create Date: 2026-04-24 16:30:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0015_plugin_im_target_routes"
down_revision: str | None = "0014_user_im_bind_tokens"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "plugin_im_target_routes",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("plugin_id", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.String(length=64), nullable=False),
        sa.Column("external_platform", sa.String(length=64), nullable=False),
        sa.Column("conversation_kind", sa.String(length=32), nullable=False),
        sa.Column("external_account_id", sa.String(length=255), nullable=False),
        sa.Column("external_conversation_id", sa.String(length=255), nullable=False),
        sa.Column("route_metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["plugin_id"], ["plugin_definitions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "plugin_id",
            "external_platform",
            "conversation_kind",
            "external_account_id",
            "external_conversation_id",
            name="uq_plugin_im_target_routes_plugin_conversation",
        ),
    )


def downgrade() -> None:
    op.drop_table("plugin_im_target_routes")
