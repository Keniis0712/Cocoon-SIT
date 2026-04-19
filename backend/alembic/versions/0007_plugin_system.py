"""add plugin system tables

Revision ID: 0007_plugin_system
Revises: 0006_idle_wakeup_runtime
Create Date: 2026-04-19
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0007_plugin_system"
down_revision = "0006_idle_wakeup_runtime"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plugin_definitions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("plugin_type", sa.String(length=32), nullable=False),
        sa.Column("entry_module", sa.String(length=255), nullable=False),
        sa.Column("service_function_name", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="disabled"),
        sa.Column("install_source", sa.String(length=32), nullable=False, server_default="zip"),
        sa.Column("data_dir", sa.String(length=1024), nullable=False),
        sa.Column("config_schema_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("default_config_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("config_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("active_version_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "plugin_versions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("plugin_id", sa.String(length=64), nullable=False),
        sa.Column("version", sa.String(length=128), nullable=False),
        sa.Column("source_zip_path", sa.String(length=1024), nullable=False),
        sa.Column("extracted_path", sa.String(length=1024), nullable=False),
        sa.Column("manifest_path", sa.String(length=1024), nullable=False),
        sa.Column("install_status", sa.String(length=32), nullable=False, server_default="installed"),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["plugin_id"], ["plugin_definitions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plugin_id", "version", name="uq_plugin_versions_plugin_id_version"),
    )

    op.create_foreign_key(
        "fk_plugin_definitions_active_version_id_plugin_versions",
        "plugin_definitions",
        "plugin_versions",
        ["active_version_id"],
        ["id"],
    )

    op.create_table(
        "plugin_event_definitions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("plugin_id", sa.String(length=64), nullable=False),
        sa.Column("plugin_version_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("function_name", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("config_schema_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("default_config_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["plugin_id"], ["plugin_definitions.id"]),
        sa.ForeignKeyConstraint(["plugin_version_id"], ["plugin_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plugin_version_id", "name", name="uq_plugin_event_definitions_version_name"),
    )

    op.create_table(
        "plugin_event_configs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("plugin_id", sa.String(length=64), nullable=False),
        sa.Column("event_name", sa.String(length=128), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("config_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["plugin_id"], ["plugin_definitions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plugin_id", "event_name", name="uq_plugin_event_configs_plugin_id_event_name"),
    )

    op.create_table(
        "plugin_run_states",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("plugin_id", sa.String(length=64), nullable=False),
        sa.Column("current_version_id", sa.String(length=64), nullable=True),
        sa.Column("process_type", sa.String(length=32), nullable=True),
        sa.Column("pid", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="stopped"),
        sa.Column("heartbeat_at", sa.String(length=64), nullable=True),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.Column("meta_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["current_version_id"], ["plugin_versions.id"]),
        sa.ForeignKeyConstraint(["plugin_id"], ["plugin_definitions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plugin_id", name="uq_plugin_run_states_plugin_id"),
    )

    op.create_table(
        "plugin_dispatch_records",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("plugin_id", sa.String(length=64), nullable=False),
        sa.Column("plugin_version_id", sa.String(length=64), nullable=False),
        sa.Column("event_name", sa.String(length=128), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.String(length=64), nullable=False),
        sa.Column("dedupe_key", sa.String(length=255), nullable=True),
        sa.Column("wakeup_task_id", sa.String(length=64), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["plugin_id"], ["plugin_definitions.id"]),
        sa.ForeignKeyConstraint(["plugin_version_id"], ["plugin_versions.id"]),
        sa.ForeignKeyConstraint(["wakeup_task_id"], ["wakeup_tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plugin_id", "event_name", "dedupe_key", name="uq_plugin_dispatch_records_dedupe"),
    )


def downgrade() -> None:
    op.drop_table("plugin_dispatch_records")
    op.drop_table("plugin_run_states")
    op.drop_table("plugin_event_configs")
    op.drop_table("plugin_event_definitions")
    op.drop_constraint("fk_plugin_definitions_active_version_id_plugin_versions", "plugin_definitions", type_="foreignkey")
    op.drop_table("plugin_versions")
    op.drop_table("plugin_definitions")
