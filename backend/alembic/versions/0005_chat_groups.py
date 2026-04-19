"""add chat group rooms and shared conversation fields

Revision ID: 0005_chat_groups
Revises: 0004_system_config
Create Date: 2026-04-19
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0005_chat_groups"
down_revision = "0004_system_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_group_rooms",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("owner_user_id", sa.String(length=64), nullable=False),
        sa.Column("character_id", sa.String(length=64), nullable=False),
        sa.Column("selected_model_id", sa.String(length=64), nullable=False),
        sa.Column("default_temperature", sa.Float(), nullable=False, server_default="0.7"),
        sa.Column("max_context_messages", sa.Integer(), nullable=False, server_default="12"),
        sa.Column("auto_compaction_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("external_platform", sa.String(length=64), nullable=True),
        sa.Column("external_group_id", sa.String(length=255), nullable=True),
        sa.Column("external_account_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], name="fk_chat_group_rooms_owner_user_id_users"),
        sa.ForeignKeyConstraint(["character_id"], ["characters.id"], name="fk_chat_group_rooms_character_id_characters"),
        sa.ForeignKeyConstraint(
            ["selected_model_id"],
            ["available_models.id"],
            name="fk_chat_group_rooms_selected_model_id_available_models",
        ),
    )
    op.create_table(
        "chat_group_members",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("room_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("member_role", sa.String(length=32), nullable=False, server_default="member"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("member_role IN ('admin', 'member')", name="ck_chat_group_members_role"),
        sa.ForeignKeyConstraint(["room_id"], ["chat_group_rooms.id"], name="fk_chat_group_members_room_id_chat_group_rooms"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_chat_group_members_user_id_users"),
    )

    with op.batch_alter_table("tag_registry") as batch_op:
        batch_op.add_column(sa.Column("visibility", sa.String(length=32), nullable=True))
    op.execute("UPDATE tag_registry SET visibility = 'private' WHERE visibility IS NULL")
    with op.batch_alter_table("tag_registry") as batch_op:
        batch_op.alter_column("visibility", existing_type=sa.String(length=32), nullable=False)

    with op.batch_alter_table("action_dispatches") as batch_op:
        batch_op.add_column(sa.Column("chat_group_id", sa.String(length=64), nullable=True))
        batch_op.alter_column("cocoon_id", existing_type=sa.String(length=64), nullable=True)
        batch_op.create_foreign_key(
            "fk_action_dispatches_chat_group_id_chat_group_rooms",
            "chat_group_rooms",
            ["chat_group_id"],
            ["id"],
        )

    with op.batch_alter_table("messages") as batch_op:
        batch_op.add_column(sa.Column("chat_group_id", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("sender_user_id", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("is_retracted", sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column("retracted_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("retracted_by_user_id", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("retraction_note", sa.Text(), nullable=True))
        batch_op.alter_column("cocoon_id", existing_type=sa.String(length=64), nullable=True)
        batch_op.create_foreign_key("fk_messages_chat_group_id_chat_group_rooms", "chat_group_rooms", ["chat_group_id"], ["id"])
        batch_op.create_foreign_key("fk_messages_sender_user_id_users", "users", ["sender_user_id"], ["id"])
        batch_op.create_foreign_key(
            "fk_messages_retracted_by_user_id_users",
            "users",
            ["retracted_by_user_id"],
            ["id"],
        )
    op.execute("UPDATE messages SET is_retracted = FALSE WHERE is_retracted IS NULL")
    with op.batch_alter_table("messages") as batch_op:
        batch_op.alter_column("is_retracted", existing_type=sa.Boolean(), nullable=False)

    with op.batch_alter_table("memory_chunks") as batch_op:
        batch_op.add_column(sa.Column("chat_group_id", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("owner_user_id", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("character_id", sa.String(length=64), nullable=True))
        batch_op.alter_column("cocoon_id", existing_type=sa.String(length=64), nullable=True)
        batch_op.create_foreign_key(
            "fk_memory_chunks_chat_group_id_chat_group_rooms",
            "chat_group_rooms",
            ["chat_group_id"],
            ["id"],
        )
        batch_op.create_foreign_key("fk_memory_chunks_owner_user_id_users", "users", ["owner_user_id"], ["id"])
        batch_op.create_foreign_key(
            "fk_memory_chunks_character_id_characters",
            "characters",
            ["character_id"],
            ["id"],
        )

    with op.batch_alter_table("failed_rounds") as batch_op:
        batch_op.add_column(sa.Column("chat_group_id", sa.String(length=64), nullable=True))
        batch_op.alter_column("cocoon_id", existing_type=sa.String(length=64), nullable=True)
        batch_op.create_foreign_key(
            "fk_failed_rounds_chat_group_id_chat_group_rooms",
            "chat_group_rooms",
            ["chat_group_id"],
            ["id"],
        )

    with op.batch_alter_table("durable_jobs") as batch_op:
        batch_op.add_column(sa.Column("chat_group_id", sa.String(length=64), nullable=True))
        batch_op.create_foreign_key(
            "fk_durable_jobs_chat_group_id_chat_group_rooms",
            "chat_group_rooms",
            ["chat_group_id"],
            ["id"],
        )

    with op.batch_alter_table("wakeup_tasks") as batch_op:
        batch_op.add_column(sa.Column("chat_group_id", sa.String(length=64), nullable=True))
        batch_op.alter_column("cocoon_id", existing_type=sa.String(length=64), nullable=True)
        batch_op.create_foreign_key(
            "fk_wakeup_tasks_chat_group_id_chat_group_rooms",
            "chat_group_rooms",
            ["chat_group_id"],
            ["id"],
        )

    with op.batch_alter_table("audit_runs") as batch_op:
        batch_op.add_column(sa.Column("chat_group_id", sa.String(length=64), nullable=True))
        batch_op.create_foreign_key(
            "fk_audit_runs_chat_group_id_chat_group_rooms",
            "chat_group_rooms",
            ["chat_group_id"],
            ["id"],
        )

    op.create_table(
        "session_states_new",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("cocoon_id", sa.String(length=64), nullable=True, unique=True),
        sa.Column("chat_group_id", sa.String(length=64), nullable=True, unique=True),
        sa.Column("relation_score", sa.Integer(), nullable=False),
        sa.Column("persona_json", sa.JSON(), nullable=False),
        sa.Column("active_tags_json", sa.JSON(), nullable=False),
        sa.Column("current_wakeup_task_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "(cocoon_id IS NOT NULL AND chat_group_id IS NULL) OR (cocoon_id IS NULL AND chat_group_id IS NOT NULL)",
            name="ck_session_states_target",
        ),
        sa.ForeignKeyConstraint(["cocoon_id"], ["cocoons.id"], name="fk_session_states_new_cocoon_id_cocoons"),
        sa.ForeignKeyConstraint(
            ["chat_group_id"],
            ["chat_group_rooms.id"],
            name="fk_session_states_new_chat_group_id_chat_group_rooms",
        ),
        sa.ForeignKeyConstraint(
            ["current_wakeup_task_id"],
            ["wakeup_tasks.id"],
            name="fk_session_states_new_current_wakeup_task_id_wakeup_tasks",
        ),
    )
    op.execute(
        """
        INSERT INTO session_states_new (
            id, cocoon_id, chat_group_id, relation_score, persona_json, active_tags_json,
            current_wakeup_task_id, created_at, updated_at
        )
        SELECT cocoon_id, cocoon_id, NULL, relation_score, persona_json, active_tags_json,
               current_wakeup_task_id, created_at, updated_at
        FROM session_states
        """
    )
    op.drop_table("session_states")
    op.rename_table("session_states_new", "session_states")


def downgrade() -> None:
    op.rename_table("session_states", "session_states_v2")
    op.create_table(
        "session_states",
        sa.Column("cocoon_id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("relation_score", sa.Integer(), nullable=False),
        sa.Column("persona_json", sa.JSON(), nullable=False),
        sa.Column("active_tags_json", sa.JSON(), nullable=False),
        sa.Column("current_wakeup_task_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["cocoon_id"], ["cocoons.id"], name="fk_session_states_cocoon_id_cocoons"),
        sa.ForeignKeyConstraint(
            ["current_wakeup_task_id"],
            ["wakeup_tasks.id"],
            name="fk_session_states_current_wakeup_task_id_wakeup_tasks",
        ),
    )
    op.execute(
        """
        INSERT INTO session_states (
            cocoon_id, relation_score, persona_json, active_tags_json, current_wakeup_task_id, created_at, updated_at
        )
        SELECT cocoon_id, relation_score, persona_json, active_tags_json, current_wakeup_task_id, created_at, updated_at
        FROM session_states_v2
        WHERE cocoon_id IS NOT NULL
        """
    )
    op.drop_table("session_states_v2")

    with op.batch_alter_table("audit_runs") as batch_op:
        batch_op.drop_constraint("fk_audit_runs_chat_group_id_chat_group_rooms", type_="foreignkey")
        batch_op.drop_column("chat_group_id")

    with op.batch_alter_table("wakeup_tasks") as batch_op:
        batch_op.drop_constraint("fk_wakeup_tasks_chat_group_id_chat_group_rooms", type_="foreignkey")
        batch_op.alter_column("cocoon_id", existing_type=sa.String(length=64), nullable=False)
        batch_op.drop_column("chat_group_id")

    with op.batch_alter_table("durable_jobs") as batch_op:
        batch_op.drop_constraint("fk_durable_jobs_chat_group_id_chat_group_rooms", type_="foreignkey")
        batch_op.drop_column("chat_group_id")

    with op.batch_alter_table("failed_rounds") as batch_op:
        batch_op.drop_constraint("fk_failed_rounds_chat_group_id_chat_group_rooms", type_="foreignkey")
        batch_op.alter_column("cocoon_id", existing_type=sa.String(length=64), nullable=False)
        batch_op.drop_column("chat_group_id")

    with op.batch_alter_table("memory_chunks") as batch_op:
        batch_op.drop_constraint("fk_memory_chunks_character_id_characters", type_="foreignkey")
        batch_op.drop_constraint("fk_memory_chunks_owner_user_id_users", type_="foreignkey")
        batch_op.drop_constraint("fk_memory_chunks_chat_group_id_chat_group_rooms", type_="foreignkey")
        batch_op.alter_column("cocoon_id", existing_type=sa.String(length=64), nullable=False)
        batch_op.drop_column("character_id")
        batch_op.drop_column("owner_user_id")
        batch_op.drop_column("chat_group_id")

    with op.batch_alter_table("messages") as batch_op:
        batch_op.drop_constraint("fk_messages_retracted_by_user_id_users", type_="foreignkey")
        batch_op.drop_constraint("fk_messages_sender_user_id_users", type_="foreignkey")
        batch_op.drop_constraint("fk_messages_chat_group_id_chat_group_rooms", type_="foreignkey")
        batch_op.alter_column("cocoon_id", existing_type=sa.String(length=64), nullable=False)
        batch_op.drop_column("retraction_note")
        batch_op.drop_column("retracted_by_user_id")
        batch_op.drop_column("retracted_at")
        batch_op.drop_column("is_retracted")
        batch_op.drop_column("sender_user_id")
        batch_op.drop_column("chat_group_id")

    with op.batch_alter_table("action_dispatches") as batch_op:
        batch_op.drop_constraint("fk_action_dispatches_chat_group_id_chat_group_rooms", type_="foreignkey")
        batch_op.alter_column("cocoon_id", existing_type=sa.String(length=64), nullable=False)
        batch_op.drop_column("chat_group_id")

    with op.batch_alter_table("tag_registry") as batch_op:
        batch_op.drop_column("visibility")

    op.drop_table("chat_group_members")
    op.drop_table("chat_group_rooms")
