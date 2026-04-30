"""add memory profiles and ops

Revision ID: 0027_mem_profiles_and_ops
Revises: 0026_user_plugin_scheds
Create Date: 2026-05-01 16:30:00
"""

from __future__ import annotations

import json

from alembic import op
import sqlalchemy as sa


revision: str = "0027_mem_profiles_and_ops"
down_revision: str | None = "0026_user_plugin_scheds"
branch_labels = None
depends_on = None


DEFAULT_MEMORY_PROFILES = {
    "reply_only": {
        "request_mode": "reply_only",
        "read_long_term_memory": True,
        "read_fact_cache": True,
        "vector_recall_limit": 20,
        "prompt_memory_limit": 5,
        "tag_match_weight": 0.05,
        "vector_weight": 0.45,
        "importance_weight": 0.25,
        "recency_weight": 0.15,
        "confidence_weight": 0.10,
        "candidate_promote_hits": 2,
        "candidate_ttl_hours": 72,
        "fact_cache_ttl_minutes": 120,
        "maintenance_decay_days": 90,
        "maintenance_decay_factor": 0.95,
        "archive_after_days": 180,
        "access_importance_boost": 0.02,
    },
    "single_pass": {
        "request_mode": "single_pass",
        "read_long_term_memory": True,
        "read_fact_cache": True,
        "vector_recall_limit": 20,
        "prompt_memory_limit": 5,
        "tag_match_weight": 0.05,
        "vector_weight": 0.45,
        "importance_weight": 0.25,
        "recency_weight": 0.15,
        "confidence_weight": 0.10,
        "candidate_promote_hits": 2,
        "candidate_ttl_hours": 72,
        "fact_cache_ttl_minutes": 120,
        "maintenance_decay_days": 90,
        "maintenance_decay_factor": 0.95,
        "archive_after_days": 180,
        "access_importance_boost": 0.02,
    },
    "meta_reply": {
        "request_mode": "meta_reply",
        "read_long_term_memory": True,
        "read_fact_cache": True,
        "vector_recall_limit": 20,
        "prompt_memory_limit": 5,
        "tag_match_weight": 0.05,
        "vector_weight": 0.45,
        "importance_weight": 0.25,
        "recency_weight": 0.15,
        "confidence_weight": 0.10,
        "candidate_promote_hits": 2,
        "candidate_ttl_hours": 72,
        "fact_cache_ttl_minutes": 120,
        "maintenance_decay_days": 90,
        "maintenance_decay_factor": 0.95,
        "archive_after_days": 180,
        "access_importance_boost": 0.02,
    },
}


def upgrade() -> None:
    with op.batch_alter_table("system_settings") as batch_op:
        batch_op.add_column(sa.Column("default_memory_profile", sa.String(length=32), nullable=False, server_default="meta_reply"))
        batch_op.add_column(sa.Column("memory_profiles_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))

    with op.batch_alter_table("cocoons") as batch_op:
        batch_op.add_column(sa.Column("memory_profile", sa.String(length=32), nullable=False, server_default="meta_reply"))

    with op.batch_alter_table("chat_group_rooms") as batch_op:
        batch_op.add_column(sa.Column("memory_profile", sa.String(length=32), nullable=False, server_default="meta_reply"))

    with op.batch_alter_table("memory_chunks") as batch_op:
        batch_op.add_column(sa.Column("memory_pool", sa.String(length=32), nullable=False, server_default="tree_private"))
        batch_op.add_column(sa.Column("memory_type", sa.String(length=32), nullable=False, server_default="summary"))
        batch_op.add_column(sa.Column("importance", sa.Integer(), nullable=False, server_default="3"))
        batch_op.add_column(sa.Column("confidence", sa.Integer(), nullable=False, server_default="3"))
        batch_op.add_column(sa.Column("status", sa.String(length=32), nullable=False, server_default="active"))
        batch_op.add_column(sa.Column("valid_until", sa.DateTime(timezone=False), nullable=True))
        batch_op.add_column(sa.Column("last_accessed_at", sa.DateTime(timezone=False), nullable=True))
        batch_op.add_column(sa.Column("access_count", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("source_kind", sa.String(length=32), nullable=False, server_default="runtime_analysis"))

    op.create_table(
        "memory_candidates",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("cocoon_id", sa.String(length=64), nullable=True),
        sa.Column("chat_group_id", sa.String(length=64), nullable=True),
        sa.Column("owner_user_id", sa.String(length=64), nullable=True),
        sa.Column("character_id", sa.String(length=64), nullable=True),
        sa.Column("memory_pool", sa.String(length=32), nullable=False, server_default="tree_private"),
        sa.Column("memory_type", sa.String(length=32), nullable=False, server_default="preference"),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tags_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("importance", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("confidence", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("hit_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("first_seen_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=False), nullable=True),
        sa.Column("meta_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.CheckConstraint(
            "NOT (cocoon_id IS NOT NULL AND chat_group_id IS NOT NULL)",
            name="ck_memory_candidates_single_target",
        ),
        sa.ForeignKeyConstraint(["character_id"], ["characters.id"], name=op.f("fk_memory_candidates_character_id")),
        sa.ForeignKeyConstraint(["chat_group_id"], ["chat_group_rooms.id"], name=op.f("fk_memory_candidates_chat_group_id")),
        sa.ForeignKeyConstraint(["cocoon_id"], ["cocoons.id"], name=op.f("fk_memory_candidates_cocoon_id")),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], name=op.f("fk_memory_candidates_owner_user_id")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_memory_candidates")),
    )

    op.create_table(
        "fact_cache_entries",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("cocoon_id", sa.String(length=64), nullable=True),
        sa.Column("chat_group_id", sa.String(length=64), nullable=True),
        sa.Column("cache_key", sa.String(length=128), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("meta_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("valid_until", sa.DateTime(timezone=False), nullable=True),
        sa.Column("last_accessed_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.CheckConstraint(
            "(cocoon_id IS NOT NULL AND chat_group_id IS NULL) OR (cocoon_id IS NULL AND chat_group_id IS NOT NULL)",
            name="ck_fact_cache_entries_target",
        ),
        sa.ForeignKeyConstraint(["chat_group_id"], ["chat_group_rooms.id"], name=op.f("fk_fact_cache_entries_chat_group_id")),
        sa.ForeignKeyConstraint(["cocoon_id"], ["cocoons.id"], name=op.f("fk_fact_cache_entries_cocoon_id")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_fact_cache_entries")),
    )

    op.create_table(
        "target_task_states",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("cocoon_id", sa.String(length=64), nullable=True),
        sa.Column("chat_group_id", sa.String(length=64), nullable=True),
        sa.Column("task_name", sa.String(length=128), nullable=True),
        sa.Column("goal", sa.Text(), nullable=True),
        sa.Column("progress", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("meta_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("expires_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.CheckConstraint(
            "(cocoon_id IS NOT NULL AND chat_group_id IS NULL) OR (cocoon_id IS NULL AND chat_group_id IS NOT NULL)",
            name="ck_target_task_states_target",
        ),
        sa.ForeignKeyConstraint(["chat_group_id"], ["chat_group_rooms.id"], name=op.f("fk_target_task_states_chat_group_id")),
        sa.ForeignKeyConstraint(["cocoon_id"], ["cocoons.id"], name=op.f("fk_target_task_states_cocoon_id")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_target_task_states")),
        sa.UniqueConstraint("cocoon_id", name=op.f("uq_target_task_states_cocoon_id")),
        sa.UniqueConstraint("chat_group_id", name=op.f("uq_target_task_states_chat_group_id")),
    )

    connection = op.get_bind()
    connection.execute(
        sa.text(
            "UPDATE system_settings SET default_memory_profile = :profile, memory_profiles_json = :profiles"
        ),
        {
            "profile": "meta_reply",
            "profiles": json.dumps(DEFAULT_MEMORY_PROFILES),
        },
    )
    connection.execute(
        sa.text(
            "UPDATE memory_chunks SET memory_pool = CASE WHEN chat_group_id IS NOT NULL THEN 'room_local' ELSE 'tree_private' END"
        )
    )


def downgrade() -> None:
    op.drop_table("target_task_states")
    op.drop_table("fact_cache_entries")
    op.drop_table("memory_candidates")

    with op.batch_alter_table("memory_chunks") as batch_op:
        batch_op.drop_column("source_kind")
        batch_op.drop_column("access_count")
        batch_op.drop_column("last_accessed_at")
        batch_op.drop_column("valid_until")
        batch_op.drop_column("status")
        batch_op.drop_column("confidence")
        batch_op.drop_column("importance")
        batch_op.drop_column("memory_type")
        batch_op.drop_column("memory_pool")

    with op.batch_alter_table("chat_group_rooms") as batch_op:
        batch_op.drop_column("memory_profile")

    with op.batch_alter_table("cocoons") as batch_op:
        batch_op.drop_column("memory_profile")

    with op.batch_alter_table("system_settings") as batch_op:
        batch_op.drop_column("memory_profiles_json")
        batch_op.drop_column("default_memory_profile")
