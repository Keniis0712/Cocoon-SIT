"""add cocoon context anchor message

Revision ID: 0022_cocoon_context_anchor
Revises: 0021_invite_quota_accounts
Create Date: 2026-04-25 22:20:00
"""

from alembic import op
import sqlalchemy as sa


revision: str = "0022_cocoon_context_anchor"
down_revision: str | None = "0021_invite_quota_accounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("cocoons") as batch_op:
        batch_op.add_column(sa.Column("context_start_message_id", sa.String(length=64), nullable=True))
        batch_op.create_foreign_key(
            "fk_cocoons_context_start_message_id_messages",
            "messages",
            ["context_start_message_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("cocoons") as batch_op:
        batch_op.drop_constraint("fk_cocoons_context_start_message_id_messages", type_="foreignkey")
        batch_op.drop_column("context_start_message_id")
