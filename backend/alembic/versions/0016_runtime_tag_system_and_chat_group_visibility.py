"""add runtime tag system fields and chat-group visibility tables

Revision ID: 0016_runtime_tag_system
Revises: 0015_plugin_im_target_routes
Create Date: 2026-04-25 12:05:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision: str = "0016_runtime_tag_system"
down_revision: str | None = "0015_plugin_im_target_routes"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


DEFAULT_TAG_ID = str(uuid4())
DEFAULT_TAG_BRIEF = "Default memory boundary automatically applied to every target."


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def upgrade() -> None:
    bind = op.get_bind()
    now = _utcnow_naive()

    with op.batch_alter_table("tag_registry") as batch_op:
        batch_op.add_column(
            sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false())
        )

    op.create_table(
        "chat_group_tag_bindings",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("chat_group_id", sa.String(length=64), nullable=False),
        sa.Column("tag_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["chat_group_id"], ["chat_group_rooms.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "tag_chat_group_visibility",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("tag_id", sa.String(length=64), nullable=False),
        sa.Column("chat_group_id", sa.String(length=64), nullable=False),
        sa.Column("is_visible", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["tag_id"], ["tag_registry.id"]),
        sa.ForeignKeyConstraint(["chat_group_id"], ["chat_group_rooms.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    default_tag_id = bind.execute(
        sa.text("SELECT id FROM tag_registry WHERE tag_id = :tag_id"),
        {"tag_id": "default"},
    ).scalar_one_or_none()

    if default_tag_id is None:
        bind.execute(
            sa.text(
                """
                INSERT INTO tag_registry (
                    id, tag_id, brief, visibility, is_isolated, is_system, meta_json, created_at, updated_at
                ) VALUES (
                    :id, :tag_id, :brief, :visibility, :is_isolated, :is_system, :meta_json, :created_at, :updated_at
                )
                """
            ),
            {
                "id": DEFAULT_TAG_ID,
                "tag_id": "default",
                "brief": DEFAULT_TAG_BRIEF,
                "visibility": "public",
                "is_isolated": False,
                "is_system": True,
                "meta_json": "{}",
                "created_at": now,
                "updated_at": now,
            },
        )
        default_tag_id = DEFAULT_TAG_ID
    else:
        bind.execute(
            sa.text(
                """
                UPDATE tag_registry
                SET is_system = TRUE,
                    visibility = 'public',
                    is_isolated = FALSE,
                    updated_at = :updated_at
                WHERE id = :id
                """
            ),
            {"id": default_tag_id, "updated_at": now},
        )

    cocoon_ids = bind.execute(sa.text("SELECT id FROM cocoons")).scalars().all()
    for cocoon_id in cocoon_ids:
        exists = bind.execute(
            sa.text(
                """
                SELECT 1
                FROM cocoon_tag_bindings
                WHERE cocoon_id = :cocoon_id AND tag_id = :tag_id
                """
            ),
            {"cocoon_id": cocoon_id, "tag_id": default_tag_id},
        ).scalar_one_or_none()
        if exists is None:
            bind.execute(
                sa.text(
                    """
                    INSERT INTO cocoon_tag_bindings (id, cocoon_id, tag_id, created_at, updated_at)
                    VALUES (:id, :cocoon_id, :tag_id, :created_at, :updated_at)
                    """
                ),
                {
                    "id": str(uuid4()),
                    "cocoon_id": cocoon_id,
                    "tag_id": default_tag_id,
                    "created_at": now,
                    "updated_at": now,
                },
            )

    chat_group_ids = bind.execute(sa.text("SELECT id FROM chat_group_rooms")).scalars().all()
    for chat_group_id in chat_group_ids:
        exists = bind.execute(
            sa.text(
                """
                SELECT 1
                FROM chat_group_tag_bindings
                WHERE chat_group_id = :chat_group_id AND tag_id = :tag_id
                """
            ),
            {"chat_group_id": chat_group_id, "tag_id": default_tag_id},
        ).scalar_one_or_none()
        if exists is None:
            bind.execute(
                sa.text(
                    """
                    INSERT INTO chat_group_tag_bindings (id, chat_group_id, tag_id, created_at, updated_at)
                    VALUES (:id, :chat_group_id, :tag_id, :created_at, :updated_at)
                    """
                ),
                {
                    "id": str(uuid4()),
                    "chat_group_id": chat_group_id,
                    "tag_id": default_tag_id,
                    "created_at": now,
                    "updated_at": now,
                },
            )


def downgrade() -> None:
    op.drop_table("tag_chat_group_visibility")
    op.drop_table("chat_group_tag_bindings")

    with op.batch_alter_table("tag_registry") as batch_op:
        batch_op.drop_column("is_system")
