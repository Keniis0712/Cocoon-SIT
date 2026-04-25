"""bind invites to groups and add root-group metadata

Revision ID: 0018_invite_group_bindings
Revises: 0017_user_permission_overrides
Create Date: 2026-04-25 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0018_invite_group_bindings"
down_revision = "0017_user_permission_overrides"
branch_labels = None
depends_on = None

ROOT_GROUP_ID = "root-group"
ROOT_GROUP_NAME = "Root Group"
ROOT_GROUP_DESCRIPTION = "Fallback group for new registrations and orphaned memberships."


def upgrade() -> None:
    with op.batch_alter_table("user_groups") as batch_op:
        batch_op.add_column(sa.Column("parent_group_id", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("description", sa.Text(), nullable=True))
        batch_op.create_foreign_key(
            "fk_user_groups_parent_group_id_user_groups",
            "user_groups",
            ["parent_group_id"],
            ["id"],
        )

    with op.batch_alter_table("invite_codes") as batch_op:
        batch_op.add_column(sa.Column("registration_group_id", sa.String(length=64), nullable=True))

    with op.batch_alter_table("invite_quota_grants") as batch_op:
        batch_op.add_column(sa.Column("revoked_at", sa.DateTime(timezone=False), nullable=True))

    op.execute(
        sa.text(
            """
            INSERT INTO user_groups (id, name, owner_user_id, parent_group_id, description, created_at, updated_at)
            SELECT :group_id, :name, NULL, NULL, :description, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            WHERE NOT EXISTS (SELECT 1 FROM user_groups WHERE id = :group_id)
            """
        ).bindparams(
            group_id=ROOT_GROUP_ID,
            name=ROOT_GROUP_NAME,
            description=ROOT_GROUP_DESCRIPTION,
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE user_groups
            SET parent_group_id = :group_id
            WHERE id <> :group_id AND parent_group_id IS NULL
            """
        ).bindparams(group_id=ROOT_GROUP_ID)
    )


def downgrade() -> None:
    with op.batch_alter_table("invite_quota_grants") as batch_op:
        batch_op.drop_column("revoked_at")

    with op.batch_alter_table("invite_codes") as batch_op:
        batch_op.drop_column("registration_group_id")

    with op.batch_alter_table("user_groups") as batch_op:
        batch_op.drop_constraint("fk_user_groups_parent_group_id_user_groups", type_="foreignkey")
        batch_op.drop_column("description")
        batch_op.drop_column("parent_group_id")
