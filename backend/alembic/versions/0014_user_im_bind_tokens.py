"""add user im bind tokens

Revision ID: 0014_user_im_bind_tokens
Revises: 0013_plugin_im_delivery_outbox
Create Date: 2026-04-24 14:30:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0014_user_im_bind_tokens"
down_revision: str | None = "0013_plugin_im_delivery_outbox"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_im_bind_tokens",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("last_validated_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_im_bind_tokens_user_id", "user_im_bind_tokens", ["user_id"], unique=False)
    op.create_index("ix_user_im_bind_tokens_expires_at", "user_im_bind_tokens", ["expires_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_user_im_bind_tokens_expires_at", table_name="user_im_bind_tokens")
    op.drop_index("ix_user_im_bind_tokens_user_id", table_name="user_im_bind_tokens")
    op.drop_table("user_im_bind_tokens")
