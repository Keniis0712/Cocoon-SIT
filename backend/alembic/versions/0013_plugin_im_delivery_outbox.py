"""add plugin im delivery outbox

Revision ID: 0013_plugin_im_delivery_outbox
Revises: 0012_remove_plugin_dedupe
Create Date: 2026-04-23 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0013_plugin_im_delivery_outbox"
down_revision = "0012_remove_plugin_dedupe"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plugin_im_delivery_outbox",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("plugin_id", sa.String(length=64), nullable=False),
        sa.Column("action_id", sa.String(length=64), nullable=True),
        sa.Column("message_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("last_error_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["action_id"], ["action_dispatches.id"]),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"]),
        sa.ForeignKeyConstraint(["plugin_id"], ["plugin_definitions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("plugin_im_delivery_outbox")
