"""move tags to user ownership and backfill plugin owners

Revision ID: 0019_user_tag_ownership
Revises: 0018_invite_group_bindings
Create Date: 2026-04-25 14:30:00
"""

from __future__ import annotations

import json
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision: str = "0019_user_tag_ownership"
down_revision: str | None = "0018_invite_group_bindings"
branch_labels = None
depends_on = None


def _new_id() -> str:
    return uuid4().hex


def _normalize_json_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except Exception:
            return []
        if isinstance(parsed, list):
            return [str(item) for item in parsed if str(item).strip()]
    return []


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    with op.batch_alter_table("tag_registry") as batch_op:
        batch_op.add_column(sa.Column("owner_user_id", sa.String(length=64), nullable=True))
        batch_op.add_column(
            sa.Column("is_hidden", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.drop_constraint("uq_tag_registry_tag_id", type_="unique")
    with op.batch_alter_table("plugin_definitions") as batch_op:
        batch_op.add_column(sa.Column("owner_user_id", sa.String(length=64), nullable=True))

    users = bind.execute(
        sa.text("SELECT id, username FROM users ORDER BY created_at ASC, id ASC")
    ).mappings().all()
    user_ids = [str(row["id"]) for row in users]
    user_by_username = {str(row["username"]): str(row["id"]) for row in users}
    fallback_user_id = (
        user_by_username.get("user1")
        or user_by_username.get("admin")
        or (user_ids[0] if user_ids else None)
    )

    if fallback_user_id:
        bind.execute(
            sa.text(
                "UPDATE plugin_definitions SET owner_user_id = :owner_user_id WHERE owner_user_id IS NULL"
            ),
            {"owner_user_id": fallback_user_id},
        )

    tag_registry = sa.table(
        "tag_registry",
        sa.column("id", sa.String(length=64)),
        sa.column("owner_user_id", sa.String(length=64)),
        sa.column("tag_id", sa.String(length=64)),
        sa.column("brief", sa.Text()),
        sa.column("visibility", sa.String(length=32)),
        sa.column("is_isolated", sa.Boolean()),
        sa.column("is_system", sa.Boolean()),
        sa.column("is_hidden", sa.Boolean()),
        sa.column("meta_json", sa.JSON()),
        sa.column("created_at", sa.DateTime()),
        sa.column("updated_at", sa.DateTime()),
    )
    cocoons = sa.table(
        "cocoons",
        sa.column("id", sa.String(length=64)),
        sa.column("owner_user_id", sa.String(length=64)),
    )
    chat_groups = sa.table(
        "chat_group_rooms",
        sa.column("id", sa.String(length=64)),
        sa.column("owner_user_id", sa.String(length=64)),
    )
    cocoon_tag_bindings = sa.table(
        "cocoon_tag_bindings",
        sa.column("id", sa.String(length=64)),
        sa.column("cocoon_id", sa.String(length=64)),
        sa.column("tag_id", sa.String(length=64)),
    )
    chat_group_tag_bindings = sa.table(
        "chat_group_tag_bindings",
        sa.column("id", sa.String(length=64)),
        sa.column("chat_group_id", sa.String(length=64)),
        sa.column("tag_id", sa.String(length=64)),
    )
    session_states = sa.table(
        "session_states",
        sa.column("id", sa.String(length=64)),
        sa.column("cocoon_id", sa.String(length=64)),
        sa.column("chat_group_id", sa.String(length=64)),
        sa.column("active_tags_json", sa.JSON()),
    )
    messages = sa.table(
        "messages",
        sa.column("id", sa.String(length=64)),
        sa.column("cocoon_id", sa.String(length=64)),
        sa.column("chat_group_id", sa.String(length=64)),
        sa.column("tags_json", sa.JSON()),
    )
    memory_chunks = sa.table(
        "memory_chunks",
        sa.column("id", sa.String(length=64)),
        sa.column("cocoon_id", sa.String(length=64)),
        sa.column("chat_group_id", sa.String(length=64)),
        sa.column("owner_user_id", sa.String(length=64)),
        sa.column("tags_json", sa.JSON()),
    )
    message_tags = sa.table(
        "message_tags",
        sa.column("id", sa.String(length=64)),
        sa.column("message_id", sa.String(length=64)),
        sa.column("tag_id", sa.String(length=64)),
    )
    memory_tags = sa.table(
        "memory_tags",
        sa.column("id", sa.String(length=64)),
        sa.column("memory_chunk_id", sa.String(length=64)),
        sa.column("tag_id", sa.String(length=64)),
    )

    old_tags = bind.execute(
        sa.select(
            tag_registry.c.id,
            tag_registry.c.tag_id,
            tag_registry.c.brief,
            tag_registry.c.meta_json,
            tag_registry.c.created_at,
            tag_registry.c.updated_at,
            tag_registry.c.is_system,
        )
    ).mappings().all()
    old_tag_by_id = {str(row["id"]): row for row in old_tags}
    cocoon_owner_map = {
        str(row["id"]): str(row["owner_user_id"])
        for row in bind.execute(sa.select(cocoons.c.id, cocoons.c.owner_user_id)).mappings().all()
    }
    chat_group_owner_map = {
        str(row["id"]): str(row["owner_user_id"])
        for row in bind.execute(sa.select(chat_groups.c.id, chat_groups.c.owner_user_id)).mappings().all()
    }
    system_source = next((row for row in old_tags if row["is_system"]), None)
    system_brief = str(system_source["brief"]) if system_source else "Default memory boundary automatically applied to every target."
    system_meta = dict(system_source["meta_json"] or {}) if system_source else {}
    system_tag_by_user: dict[str, str] = {}
    migrated_tag_by_old_owner: dict[tuple[str, str], str] = {}

    def ensure_system_tag(user_id: str) -> str:
        existing = system_tag_by_user.get(user_id)
        if existing:
            return existing
        next_id = _new_id()
        bind.execute(
            tag_registry.insert().values(
                id=next_id,
                owner_user_id=user_id,
                tag_id="default",
                brief=system_brief,
                visibility="private",
                is_isolated=True,
                is_system=True,
                is_hidden=True,
                meta_json={**system_meta, "system": True},
                created_at=system_source["created_at"] if system_source else None,
                updated_at=system_source["updated_at"] if system_source else None,
            )
        )
        system_tag_by_user[user_id] = next_id
        return next_id

    def ensure_owned_copy(old_tag_id: str, owner_user_id: str | None) -> str | None:
        if not owner_user_id:
            return None
        source = old_tag_by_id.get(old_tag_id)
        if not source:
            return None
        if source["is_system"]:
            return ensure_system_tag(owner_user_id)
        key = (old_tag_id, owner_user_id)
        existing = migrated_tag_by_old_owner.get(key)
        if existing:
            return existing
        next_id = _new_id()
        bind.execute(
            tag_registry.insert().values(
                id=next_id,
                owner_user_id=owner_user_id,
                tag_id=str(source["tag_id"]),
                brief=str(source["brief"]),
                visibility="private",
                is_isolated=True,
                is_system=False,
                is_hidden=False,
                meta_json=dict(source["meta_json"] or {}),
                created_at=source["created_at"],
                updated_at=source["updated_at"],
            )
        )
        migrated_tag_by_old_owner[key] = next_id
        return next_id

    for user_id in user_ids:
        ensure_system_tag(user_id)

    for row in bind.execute(
        sa.select(
            cocoon_tag_bindings.c.id,
            cocoon_tag_bindings.c.cocoon_id,
            cocoon_tag_bindings.c.tag_id,
        )
    ).mappings().all():
        owner_user_id = cocoon_owner_map.get(str(row["cocoon_id"])) or fallback_user_id
        next_tag_id = ensure_owned_copy(str(row["tag_id"]), owner_user_id)
        if next_tag_id:
            bind.execute(
                cocoon_tag_bindings.update()
                .where(cocoon_tag_bindings.c.id == row["id"])
                .values(tag_id=next_tag_id)
            )

    for row in bind.execute(
        sa.select(
            chat_group_tag_bindings.c.id,
            chat_group_tag_bindings.c.chat_group_id,
            chat_group_tag_bindings.c.tag_id,
        )
    ).mappings().all():
        owner_user_id = chat_group_owner_map.get(str(row["chat_group_id"])) or fallback_user_id
        next_tag_id = ensure_owned_copy(str(row["tag_id"]), owner_user_id)
        if next_tag_id:
            bind.execute(
                chat_group_tag_bindings.update()
                .where(chat_group_tag_bindings.c.id == row["id"])
                .values(tag_id=next_tag_id)
            )

    for row in bind.execute(
        sa.select(
            session_states.c.id,
            session_states.c.cocoon_id,
            session_states.c.chat_group_id,
            session_states.c.active_tags_json,
        )
    ).mappings().all():
        owner_user_id = (
            cocoon_owner_map.get(str(row["cocoon_id"])) if row["cocoon_id"] else None
        ) or (
            chat_group_owner_map.get(str(row["chat_group_id"])) if row["chat_group_id"] else None
        ) or fallback_user_id
        next_refs: list[str] = []
        for old_tag_id in _normalize_json_list(row["active_tags_json"]):
            next_tag_id = ensure_owned_copy(old_tag_id, owner_user_id)
            if next_tag_id and next_tag_id not in next_refs:
                next_refs.append(next_tag_id)
        if owner_user_id:
            system_tag_id = ensure_system_tag(owner_user_id)
            if system_tag_id not in next_refs:
                next_refs.insert(0, system_tag_id)
        bind.execute(
            session_states.update()
            .where(session_states.c.id == row["id"])
            .values(active_tags_json=next_refs)
        )

    message_owner_map: dict[str, str | None] = {}
    for row in bind.execute(
        sa.select(
            messages.c.id,
            messages.c.cocoon_id,
            messages.c.chat_group_id,
            messages.c.tags_json,
        )
    ).mappings().all():
        owner_user_id = (
            cocoon_owner_map.get(str(row["cocoon_id"])) if row["cocoon_id"] else None
        ) or (
            chat_group_owner_map.get(str(row["chat_group_id"])) if row["chat_group_id"] else None
        ) or fallback_user_id
        message_owner_map[str(row["id"])] = owner_user_id
        next_refs: list[str] = []
        for old_tag_id in _normalize_json_list(row["tags_json"]):
            next_tag_id = ensure_owned_copy(old_tag_id, owner_user_id)
            if next_tag_id and next_tag_id not in next_refs:
                next_refs.append(next_tag_id)
        bind.execute(
            messages.update()
            .where(messages.c.id == row["id"])
            .values(tags_json=next_refs)
        )

    memory_owner_map: dict[str, str | None] = {}
    for row in bind.execute(
        sa.select(
            memory_chunks.c.id,
            memory_chunks.c.cocoon_id,
            memory_chunks.c.chat_group_id,
            memory_chunks.c.owner_user_id,
            memory_chunks.c.tags_json,
        )
    ).mappings().all():
        owner_user_id = (str(row["owner_user_id"]) if row["owner_user_id"] else None) or (
            cocoon_owner_map.get(str(row["cocoon_id"])) if row["cocoon_id"] else None
        ) or (
            chat_group_owner_map.get(str(row["chat_group_id"])) if row["chat_group_id"] else None
        ) or fallback_user_id
        memory_owner_map[str(row["id"])] = owner_user_id
        next_refs: list[str] = []
        for old_tag_id in _normalize_json_list(row["tags_json"]):
            next_tag_id = ensure_owned_copy(old_tag_id, owner_user_id)
            if next_tag_id and next_tag_id not in next_refs:
                next_refs.append(next_tag_id)
        bind.execute(
            memory_chunks.update()
            .where(memory_chunks.c.id == row["id"])
            .values(tags_json=next_refs)
        )

    for row in bind.execute(
        sa.select(message_tags.c.id, message_tags.c.message_id, message_tags.c.tag_id)
    ).mappings().all():
        owner_user_id = message_owner_map.get(str(row["message_id"])) or fallback_user_id
        next_tag_id = ensure_owned_copy(str(row["tag_id"]), owner_user_id)
        if next_tag_id:
            bind.execute(
                message_tags.update()
                .where(message_tags.c.id == row["id"])
                .values(tag_id=next_tag_id)
            )

    for row in bind.execute(
        sa.select(memory_tags.c.id, memory_tags.c.memory_chunk_id, memory_tags.c.tag_id)
    ).mappings().all():
        owner_user_id = memory_owner_map.get(str(row["memory_chunk_id"])) or fallback_user_id
        next_tag_id = ensure_owned_copy(str(row["tag_id"]), owner_user_id)
        if next_tag_id:
            bind.execute(
                memory_tags.update()
                .where(memory_tags.c.id == row["id"])
                .values(tag_id=next_tag_id)
            )

    bind.execute(sa.text("DELETE FROM tag_chat_group_visibility"))

    if fallback_user_id:
        for row in old_tags:
            if row["is_system"]:
                continue
            ensure_owned_copy(str(row["id"]), fallback_user_id)

    if old_tags:
        bind.execute(
            tag_registry.delete().where(
                tag_registry.c.id.in_([str(row["id"]) for row in old_tags])
            )
        )

    with op.batch_alter_table("tag_registry") as batch_op:
        batch_op.create_foreign_key(
            "fk_tag_registry_owner_user_id_users",
            "users",
            ["owner_user_id"],
            ["id"],
        )
        batch_op.alter_column("owner_user_id", existing_type=sa.String(length=64), nullable=False)
        batch_op.create_unique_constraint(
            "uq_tag_registry_owner_tag_id",
            ["owner_user_id", "tag_id"],
        )
    with op.batch_alter_table("plugin_definitions") as batch_op:
        batch_op.create_foreign_key(
            "fk_plugin_definitions_owner_user_id_users",
            "users",
            ["owner_user_id"],
            ["id"],
        )

    if dialect == "postgresql":
        op.execute("ALTER TABLE tag_registry ALTER COLUMN is_hidden DROP DEFAULT")
    else:
        with op.batch_alter_table("tag_registry") as batch_op:
            batch_op.alter_column("is_hidden", server_default=None)


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported for 0019_user_tag_ownership")
