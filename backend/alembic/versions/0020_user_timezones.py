"""add timezone to users

Revision ID: 0020_user_timezones
Revises: 0019_user_tag_ownership
Create Date: 2026-04-25 19:30:00
"""

from alembic import op
import sqlalchemy as sa


revision: str = "0020_user_timezones"
down_revision: str | None = "0019_user_tag_ownership"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column("timezone", sa.String(length=128), nullable=False, server_default="UTC")
        )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("timezone")
