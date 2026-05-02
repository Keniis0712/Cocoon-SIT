"""add user group scopes

Revision ID: 0029_user_group_scopes
Revises: 0028_mem_kw_cache
Create Date: 2026-05-02 11:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app.models.identity import new_id


revision: str = "0029_user_group_scopes"
down_revision: str | None = "0028_mem_kw_cache"
branch_labels = None
depends_on = None

ROOT_GROUP_ID = "root-group"
ROOT_GROUP_NAME = "Root Group"
ROOT_GROUP_DESCRIPTION = "Fallback group for new registrations and orphaned memberships."


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("primary_group_id", sa.String(length=64), nullable=True))
        batch_op.create_foreign_key(
            "fk_users_primary_group_id_user_groups",
            "user_groups",
            ["primary_group_id"],
            ["id"],
        )

    op.create_table(
        "user_group_management_grants",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("group_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["user_groups.id"], name=op.f("fk_user_group_management_grants_group_id")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_user_group_management_grants_user_id")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_group_management_grants")),
        sa.UniqueConstraint("user_id", "group_id", name="uq_user_group_management_user_group"),
    )

    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            INSERT INTO user_groups (id, name, owner_user_id, parent_group_id, description, created_at, updated_at)
            SELECT :group_id, :name, NULL, NULL, :description, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            WHERE NOT EXISTS (SELECT 1 FROM user_groups WHERE id = :group_id)
            """
        ),
        {
            "group_id": ROOT_GROUP_ID,
            "name": ROOT_GROUP_NAME,
            "description": ROOT_GROUP_DESCRIPTION,
        },
    )
    connection.execute(
        sa.text("UPDATE users SET primary_group_id = :group_id WHERE primary_group_id IS NULL"),
        {"group_id": ROOT_GROUP_ID},
    )

    duplicate_memberships = connection.execute(
        sa.text(
            """
            SELECT group_id, user_id, MIN(id) AS keep_id
            FROM user_group_members
            GROUP BY group_id, user_id
            HAVING COUNT(*) > 1
            """
        )
    ).mappings().all()
    for row in duplicate_memberships:
        connection.execute(
            sa.text(
                """
                DELETE FROM user_group_members
                WHERE group_id = :group_id
                  AND user_id = :user_id
                  AND id <> :keep_id
                """
            ),
            {
                "group_id": row["group_id"],
                "user_id": row["user_id"],
                "keep_id": row["keep_id"],
            },
        )

    with op.batch_alter_table("user_group_members") as batch_op:
        batch_op.create_unique_constraint(
            "uq_user_group_members_group_user",
            ["group_id", "user_id"],
        )

    connection.execute(sa.text("UPDATE character_acl SET subject_type = UPPER(subject_type)"))

    characters = connection.execute(
        sa.text("SELECT id, settings_json FROM characters ORDER BY created_at ASC")
    ).mappings().all()
    public_character_ids = []
    for row in characters:
        settings_json = row.get("settings_json") or {}
        if isinstance(settings_json, dict) and str(settings_json.get("visibility") or "").lower() == "public":
            public_character_ids.append(row["id"])

    existing_public_acl_ids = {
        row["character_id"]
        for row in connection.execute(
            sa.text(
                """
                SELECT character_id
                FROM character_acl
                WHERE subject_type = 'AUTHENTICATED_ALL'
                """
            )
        ).mappings().all()
    }
    for character_id in public_character_ids:
        if character_id in existing_public_acl_ids:
            connection.execute(
                sa.text(
                    """
                    UPDATE character_acl
                    SET can_read = TRUE,
                        can_use = FALSE,
                        subject_id = :subject_id
                    WHERE character_id = :character_id
                      AND subject_type = 'AUTHENTICATED_ALL'
                    """
                ),
                {"character_id": character_id, "subject_id": "*"},
            )
            continue
        connection.execute(
            sa.text(
                """
                INSERT INTO character_acl (
                    id,
                    character_id,
                    subject_type,
                    subject_id,
                    can_read,
                    can_use,
                    created_at,
                    updated_at
                ) VALUES (
                    :id,
                    :character_id,
                    'AUTHENTICATED_ALL',
                    :subject_id,
                    TRUE,
                    FALSE,
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                )
                """
            ),
            {
                "id": new_id(),
                "character_id": character_id,
                "subject_id": "*",
            },
        )


def downgrade() -> None:
    with op.batch_alter_table("user_group_members") as batch_op:
        batch_op.drop_constraint("uq_user_group_members_group_user", type_="unique")

    op.drop_table("user_group_management_grants")

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("fk_users_primary_group_id_user_groups", type_="foreignkey")
        batch_op.drop_column("primary_group_id")
