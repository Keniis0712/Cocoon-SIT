"""move plugin schedules to users

Revision ID: 0026_user_plugin_scheds
Revises: 0025_group_chat_agg
Create Date: 2026-04-30 15:00:00
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision: str = "0026_user_plugin_scheds"
down_revision: str | None = "0025_group_chat_agg"
branch_labels = None
depends_on = None


plugin_event_configs = sa.table(
    "plugin_event_configs",
    sa.column("id", sa.String()),
    sa.column("plugin_id", sa.String()),
    sa.column("event_name", sa.String()),
    sa.column("schedule_mode", sa.String()),
    sa.column("schedule_interval_seconds", sa.Integer()),
    sa.column("schedule_cron", sa.String()),
    sa.column("created_at", sa.DateTime()),
    sa.column("updated_at", sa.DateTime()),
)

plugin_definitions = sa.table(
    "plugin_definitions",
    sa.column("id", sa.String()),
    sa.column("owner_user_id", sa.String()),
)

plugin_user_event_configs = sa.table(
    "plugin_user_event_configs",
    sa.column("id", sa.String()),
    sa.column("plugin_id", sa.String()),
    sa.column("user_id", sa.String()),
    sa.column("event_name", sa.String()),
    sa.column("schedule_mode", sa.String()),
    sa.column("schedule_interval_seconds", sa.Integer()),
    sa.column("schedule_cron", sa.String()),
    sa.column("created_at", sa.DateTime()),
    sa.column("updated_at", sa.DateTime()),
)


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def upgrade() -> None:
    op.create_table(
        "plugin_user_event_configs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("plugin_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("event_name", sa.String(length=128), nullable=False),
        sa.Column("schedule_mode", sa.String(length=32), nullable=False, server_default="manual"),
        sa.Column("schedule_interval_seconds", sa.Integer(), nullable=True),
        sa.Column("schedule_cron", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["plugin_id"], ["plugin_definitions.id"], name=op.f("fk_plugin_user_event_configs_plugin_id")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_plugin_user_event_configs_user_id")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plugin_user_event_configs")),
        sa.UniqueConstraint(
            "plugin_id",
            "user_id",
            "event_name",
            name="uq_plugin_user_event_configs_plugin_id_user_id_event_name",
        ),
    )

    connection = op.get_bind()
    rows = connection.execute(
        sa.select(
            plugin_event_configs.c.plugin_id,
            plugin_event_configs.c.event_name,
            plugin_event_configs.c.schedule_mode,
            plugin_event_configs.c.schedule_interval_seconds,
            plugin_event_configs.c.schedule_cron,
            plugin_event_configs.c.created_at,
            plugin_event_configs.c.updated_at,
            plugin_definitions.c.owner_user_id,
        ).select_from(
            plugin_event_configs.join(
                plugin_definitions,
                plugin_definitions.c.id == plugin_event_configs.c.plugin_id,
            )
        )
    ).mappings()
    for row in rows:
        if not row["owner_user_id"]:
            continue
        if (row["schedule_mode"] or "manual") == "manual":
            continue
        connection.execute(
            plugin_user_event_configs.insert().values(
                id=str(uuid4()),
                plugin_id=row["plugin_id"],
                user_id=row["owner_user_id"],
                event_name=row["event_name"],
                schedule_mode=row["schedule_mode"] or "manual",
                schedule_interval_seconds=row["schedule_interval_seconds"],
                schedule_cron=row["schedule_cron"],
                created_at=row["created_at"] or _utcnow(),
                updated_at=row["updated_at"] or _utcnow(),
            )
        )

    with op.batch_alter_table("plugin_event_configs") as batch_op:
        batch_op.drop_column("schedule_cron")
        batch_op.drop_column("schedule_interval_seconds")
        batch_op.drop_column("schedule_mode")


def downgrade() -> None:
    with op.batch_alter_table("plugin_event_configs") as batch_op:
        batch_op.add_column(
            sa.Column("schedule_mode", sa.String(length=32), nullable=False, server_default="manual")
        )
        batch_op.add_column(sa.Column("schedule_interval_seconds", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("schedule_cron", sa.String(length=255), nullable=True))

    connection = op.get_bind()
    rows = connection.execute(
        sa.select(
            plugin_user_event_configs.c.plugin_id,
            plugin_user_event_configs.c.event_name,
            plugin_user_event_configs.c.schedule_mode,
            plugin_user_event_configs.c.schedule_interval_seconds,
            plugin_user_event_configs.c.schedule_cron,
            plugin_definitions.c.owner_user_id,
        ).select_from(
            plugin_user_event_configs.join(
                plugin_definitions,
                sa.and_(
                    plugin_definitions.c.id == plugin_user_event_configs.c.plugin_id,
                    plugin_definitions.c.owner_user_id == plugin_user_event_configs.c.user_id,
                ),
            )
        )
    ).mappings()
    for row in rows:
        connection.execute(
            plugin_event_configs.update()
            .where(
                sa.and_(
                    plugin_event_configs.c.plugin_id == row["plugin_id"],
                    plugin_event_configs.c.event_name == row["event_name"],
                )
            )
            .values(
                schedule_mode=row["schedule_mode"] or "manual",
                schedule_interval_seconds=row["schedule_interval_seconds"],
                schedule_cron=row["schedule_cron"],
            )
        )

    op.drop_table("plugin_user_event_configs")
