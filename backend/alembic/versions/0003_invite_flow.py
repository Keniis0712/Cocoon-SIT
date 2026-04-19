"""extend invite management flow

Revision ID: 0003_invite_flow
Revises: 0002_vector_runtime
Create Date: 2026-04-18
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0003_invite_flow"
down_revision = "0002_vector_runtime"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("invite_codes") as batch_op:
        batch_op.add_column(sa.Column("created_for_user_id", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("source_type", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("source_id", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("revoked_at", sa.DateTime(), nullable=True))
        batch_op.create_foreign_key(
            "fk_invite_codes_created_for_user_id_users",
            "users",
            ["created_for_user_id"],
            ["id"],
        )

    op.execute("UPDATE invite_codes SET source_type = 'ADMIN_OVERRIDE' WHERE source_type IS NULL")
    op.execute("UPDATE invite_codes SET created_for_user_id = created_by_user_id WHERE created_for_user_id IS NULL")

    with op.batch_alter_table("invite_codes") as batch_op:
        batch_op.alter_column("source_type", existing_type=sa.String(length=32), nullable=False)

    with op.batch_alter_table("invite_quota_grants") as batch_op:
        batch_op.add_column(sa.Column("granted_by_user_id", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("source_type", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("source_id", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("target_type", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("target_id", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("is_unlimited", sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column("note", sa.Text(), nullable=True))
        batch_op.alter_column("invite_code_id", existing_type=sa.String(length=64), nullable=True)
        batch_op.alter_column("user_id", existing_type=sa.String(length=64), nullable=True)
        batch_op.create_foreign_key(
            "fk_invite_quota_grants_granted_by_user_id_users",
            "users",
            ["granted_by_user_id"],
            ["id"],
        )

    op.execute("UPDATE invite_quota_grants SET source_type = 'ADMIN_OVERRIDE' WHERE source_type IS NULL")
    op.execute("UPDATE invite_quota_grants SET target_type = 'USER' WHERE target_type IS NULL")
    op.execute("UPDATE invite_quota_grants SET target_id = user_id WHERE target_id IS NULL")
    op.execute("UPDATE invite_quota_grants SET is_unlimited = FALSE WHERE is_unlimited IS NULL")

    with op.batch_alter_table("invite_quota_grants") as batch_op:
        batch_op.alter_column("source_type", existing_type=sa.String(length=32), nullable=False)
        batch_op.alter_column("target_type", existing_type=sa.String(length=32), nullable=False)
        batch_op.alter_column("target_id", existing_type=sa.String(length=64), nullable=False)
        batch_op.alter_column("is_unlimited", existing_type=sa.Boolean(), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("invite_quota_grants") as batch_op:
        batch_op.drop_constraint("fk_invite_quota_grants_granted_by_user_id_users", type_="foreignkey")
        batch_op.alter_column("invite_code_id", existing_type=sa.String(length=64), nullable=False)
        batch_op.alter_column("user_id", existing_type=sa.String(length=64), nullable=False)
        batch_op.drop_column("note")
        batch_op.drop_column("is_unlimited")
        batch_op.drop_column("target_id")
        batch_op.drop_column("target_type")
        batch_op.drop_column("source_id")
        batch_op.drop_column("source_type")
        batch_op.drop_column("granted_by_user_id")

    with op.batch_alter_table("invite_codes") as batch_op:
        batch_op.drop_constraint("fk_invite_codes_created_for_user_id_users", type_="foreignkey")
        batch_op.drop_column("revoked_at")
        batch_op.drop_column("source_id")
        batch_op.drop_column("source_type")
        batch_op.drop_column("created_for_user_id")
