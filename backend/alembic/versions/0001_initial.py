"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-18
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s",
    "pk": "pk_%(table_name)s",
}


def build_metadata() -> sa.MetaData:
    metadata = sa.MetaData(naming_convention=NAMING_CONVENTION)

    sa.Table(
        "roles",
        metadata,
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("permissions_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_roles"),
        sa.UniqueConstraint("name", name="uq_roles_name"),
    )

    sa.Table(
        "users",
        metadata,
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role_id", sa.String(length=64), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], name="fk_users_role_id_roles"),
        sa.UniqueConstraint("username", name="uq_users_username"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    sa.Table(
        "auth_sessions",
        metadata,
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_auth_sessions"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_auth_sessions_user_id_users"),
    )

    sa.Table(
        "invite_codes",
        metadata,
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=64), nullable=True),
        sa.Column("quota_total", sa.Integer(), nullable=False),
        sa.Column("quota_used", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_invite_codes"),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], name="fk_invite_codes_created_by_user_id_users"
        ),
        sa.UniqueConstraint("code", name="uq_invite_codes_code"),
    )

    sa.Table(
        "invite_quota_grants",
        metadata,
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("invite_code_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("quota", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_invite_quota_grants_user_id_users"),
        sa.PrimaryKeyConstraint("id", name="pk_invite_quota_grants"),
        sa.ForeignKeyConstraint(
            ["invite_code_id"], ["invite_codes.id"], name="fk_invite_quota_grants_invite_code_id_invite_codes"
        ),
    )

    sa.Table(
        "user_groups",
        metadata,
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("owner_user_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_user_groups"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], name="fk_user_groups_owner_user_id_users"),
    )

    sa.Table(
        "user_group_members",
        metadata,
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("group_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("member_role", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["user_groups.id"], name="fk_user_group_members_group_id_user_groups"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_user_group_members_user_id_users"),
        sa.PrimaryKeyConstraint("id", name="pk_user_group_members"),
    )

    sa.Table(
        "audit_runs",
        metadata,
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("cocoon_id", sa.String(length=64), nullable=True),
        sa.Column("action_id", sa.String(length=64), nullable=True),
        sa.Column("operation_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("trigger_event_uid", sa.String(length=128), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["action_id"], ["action_dispatches.id"], name="fk_audit_runs_action_id_action_dispatches"),
        sa.ForeignKeyConstraint(["cocoon_id"], ["cocoons.id"], name="fk_audit_runs_cocoon_id_cocoons"),
        sa.PrimaryKeyConstraint("id", name="pk_audit_runs"),
    )

    sa.Table(
        "audit_steps",
        metadata,
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("step_name", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("meta_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["audit_runs.id"], name="fk_audit_steps_run_id_audit_runs"),
        sa.PrimaryKeyConstraint("id", name="pk_audit_steps"),
    )

    sa.Table(
        "audit_artifacts",
        metadata,
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("step_id", sa.String(length=64), nullable=True),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("storage_backend", sa.String(length=32), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["audit_runs.id"], name="fk_audit_artifacts_run_id_audit_runs"),
        sa.PrimaryKeyConstraint("id", name="pk_audit_artifacts"),
        sa.ForeignKeyConstraint(["step_id"], ["audit_steps.id"], name="fk_audit_artifacts_step_id_audit_steps"),
    )

    sa.Table(
        "audit_links",
        metadata,
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("source_artifact_id", sa.String(length=64), nullable=True),
        sa.Column("source_step_id", sa.String(length=64), nullable=True),
        sa.Column("target_artifact_id", sa.String(length=64), nullable=True),
        sa.Column("target_step_id", sa.String(length=64), nullable=True),
        sa.Column("relation", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_audit_links"),
        sa.ForeignKeyConstraint(["target_step_id"], ["audit_steps.id"], name="fk_audit_links_target_step_id_audit_steps"),
        sa.ForeignKeyConstraint(["source_step_id"], ["audit_steps.id"], name="fk_audit_links_source_step_id_audit_steps"),
        sa.ForeignKeyConstraint(["run_id"], ["audit_runs.id"], name="fk_audit_links_run_id_audit_runs"),
        sa.ForeignKeyConstraint(
            ["target_artifact_id"], ["audit_artifacts.id"], name="fk_audit_links_target_artifact_id_audit_artifacts"
        ),
        sa.ForeignKeyConstraint(
            ["source_artifact_id"], ["audit_artifacts.id"], name="fk_audit_links_source_artifact_id_audit_artifacts"
        ),
    )

    sa.Table(
        "characters",
        metadata,
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("prompt_summary", sa.Text(), nullable=False),
        sa.Column("settings_json", sa.JSON(), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_characters"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], name="fk_characters_created_by_user_id_users"),
    )

    sa.Table(
        "character_acl",
        metadata,
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("character_id", sa.String(length=64), nullable=False),
        sa.Column("subject_type", sa.String(length=32), nullable=False),
        sa.Column("subject_id", sa.String(length=64), nullable=False),
        sa.Column("can_read", sa.Boolean(), nullable=False),
        sa.Column("can_use", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_character_acl"),
        sa.ForeignKeyConstraint(["character_id"], ["characters.id"], name="fk_character_acl_character_id_characters"),
    )

    sa.Table(
        "model_providers",
        metadata,
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("base_url", sa.String(length=512), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("capabilities_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("name", name="uq_model_providers_name"),
        sa.PrimaryKeyConstraint("id", name="pk_model_providers"),
    )

    sa.Table(
        "available_models",
        metadata,
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("provider_id", sa.String(length=64), nullable=False),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("model_kind", sa.String(length=64), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["provider_id"], ["model_providers.id"], name="fk_available_models_provider_id_model_providers"),
        sa.PrimaryKeyConstraint("id", name="pk_available_models"),
    )

    sa.Table(
        "embedding_providers",
        metadata,
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("provider_id", sa.String(length=64), nullable=True),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_embedding_providers"),
        sa.UniqueConstraint("name", name="uq_embedding_providers_name"),
        sa.ForeignKeyConstraint(["provider_id"], ["model_providers.id"], name="fk_embedding_providers_provider_id_model_providers"),
    )

    sa.Table(
        "provider_credentials",
        metadata,
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("provider_id", sa.String(length=64), nullable=False),
        sa.Column("secret_encrypted", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("provider_id", name="uq_provider_credentials_provider_id"),
        sa.PrimaryKeyConstraint("id", name="pk_provider_credentials"),
        sa.ForeignKeyConstraint(["provider_id"], ["model_providers.id"], name="fk_provider_credentials_provider_id_model_providers"),
    )

    sa.Table(
        "tag_registry",
        metadata,
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("tag_id", sa.String(length=64), nullable=False),
        sa.Column("brief", sa.Text(), nullable=False),
        sa.Column("is_isolated", sa.Boolean(), nullable=False),
        sa.Column("meta_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tag_id", name="uq_tag_registry_tag_id"),
        sa.PrimaryKeyConstraint("id", name="pk_tag_registry"),
    )

    sa.Table(
        "action_dispatches",
        metadata,
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("cocoon_id", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("client_request_id", sa.String(length=128), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.Column("queued_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_action_dispatches"),
        sa.ForeignKeyConstraint(
            ["cocoon_id"], ["cocoons.id"], name="fk_action_dispatches_cocoon_id_cocoons", use_alter=True
        ),
        sa.UniqueConstraint("client_request_id", name="uq_action_dispatches_client_request_id"),
    )

    sa.Table(
        "durable_jobs",
        metadata,
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("cocoon_id", sa.String(length=64), nullable=True),
        sa.Column("job_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("lock_key", sa.String(length=128), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("available_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("worker_name", sa.String(length=64), nullable=True),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_durable_jobs"),
        sa.ForeignKeyConstraint(["cocoon_id"], ["cocoons.id"], name="fk_durable_jobs_cocoon_id_cocoons"),
    )

    sa.Table(
        "wakeup_tasks",
        metadata,
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("cocoon_id", sa.String(length=64), nullable=False),
        sa.Column("run_at", sa.DateTime(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["cocoon_id"], ["cocoons.id"], name="fk_wakeup_tasks_cocoon_id_cocoons"),
        sa.PrimaryKeyConstraint("id", name="pk_wakeup_tasks"),
    )

    sa.Table(
        "cocoon_pull_jobs",
        metadata,
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("durable_job_id", sa.String(length=64), nullable=False),
        sa.Column("source_cocoon_id", sa.String(length=64), nullable=False),
        sa.Column("target_cocoon_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("summary_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_cocoon_pull_jobs"),
        sa.ForeignKeyConstraint(["source_cocoon_id"], ["cocoons.id"], name="fk_cocoon_pull_jobs_source_cocoon_id_cocoons"),
        sa.ForeignKeyConstraint(["durable_job_id"], ["durable_jobs.id"], name="fk_cocoon_pull_jobs_durable_job_id_durable_jobs"),
        sa.ForeignKeyConstraint(["target_cocoon_id"], ["cocoons.id"], name="fk_cocoon_pull_jobs_target_cocoon_id_cocoons"),
    )

    sa.Table(
        "cocoon_merge_jobs",
        metadata,
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("durable_job_id", sa.String(length=64), nullable=False),
        sa.Column("source_cocoon_id", sa.String(length=64), nullable=False),
        sa.Column("target_cocoon_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("summary_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["target_cocoon_id"], ["cocoons.id"], name="fk_cocoon_merge_jobs_target_cocoon_id_cocoons"),
        sa.PrimaryKeyConstraint("id", name="pk_cocoon_merge_jobs"),
        sa.ForeignKeyConstraint(["source_cocoon_id"], ["cocoons.id"], name="fk_cocoon_merge_jobs_source_cocoon_id_cocoons"),
        sa.ForeignKeyConstraint(["durable_job_id"], ["durable_jobs.id"], name="fk_cocoon_merge_jobs_durable_job_id_durable_jobs"),
    )

    sa.Table(
        "checkpoints",
        metadata,
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("cocoon_id", sa.String(length=64), nullable=False),
        sa.Column("anchor_message_id", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=128), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_checkpoints"),
        sa.ForeignKeyConstraint(["anchor_message_id"], ["messages.id"], name="fk_checkpoints_anchor_message_id_messages"),
        sa.ForeignKeyConstraint(["cocoon_id"], ["cocoons.id"], name="fk_checkpoints_cocoon_id_cocoons"),
    )

    sa.Table(
        "prompt_templates",
        metadata,
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("template_type", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("active_revision_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["active_revision_id"],
            ["prompt_template_revisions.id"],
            name="fk_prompt_templates_active_revision_id",
            use_alter=True,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_prompt_templates"),
        sa.UniqueConstraint("template_type", name="uq_prompt_templates_template_type"),
    )

    sa.Table(
        "prompt_template_revisions",
        metadata,
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("template_id", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("variables_json", sa.JSON(), nullable=False),
        sa.Column("checksum", sa.String(length=128), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], name="fk_prompt_template_revisions_created_by_user_id_users"
        ),
        sa.ForeignKeyConstraint(
            ["template_id"], ["prompt_templates.id"], name="fk_prompt_template_revisions_template_id_prompt_templates", use_alter=True
        ),
        sa.PrimaryKeyConstraint("id", name="pk_prompt_template_revisions"),
    )

    sa.Table(
        "prompt_variables",
        metadata,
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("template_type", sa.String(length=64), nullable=False),
        sa.Column("variable_name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_prompt_variables"),
    )

    sa.Table(
        "cocoons",
        metadata,
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("parent_id", sa.String(length=64), nullable=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("owner_user_id", sa.String(length=64), nullable=False),
        sa.Column("character_id", sa.String(length=64), nullable=False),
        sa.Column("selected_model_id", sa.String(length=64), nullable=False),
        sa.Column("summary_model_id", sa.String(length=64), nullable=True),
        sa.Column("default_temperature", sa.Float(), nullable=False),
        sa.Column("max_context_messages", sa.Integer(), nullable=False),
        sa.Column("auto_compaction_enabled", sa.Boolean(), nullable=False),
        sa.Column("rollback_anchor_msg_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["summary_model_id"], ["available_models.id"], name="fk_cocoons_summary_model_id_available_models"),
        sa.ForeignKeyConstraint(["character_id"], ["characters.id"], name="fk_cocoons_character_id_characters"),
        sa.ForeignKeyConstraint(["parent_id"], ["cocoons.id"], name="fk_cocoons_parent_id_cocoons"),
        sa.PrimaryKeyConstraint("id", name="pk_cocoons"),
        sa.ForeignKeyConstraint(
            ["rollback_anchor_msg_id"], ["messages.id"], name="fk_cocoons_rollback_anchor_msg_id_messages", use_alter=True
        ),
        sa.ForeignKeyConstraint(["selected_model_id"], ["available_models.id"], name="fk_cocoons_selected_model_id_available_models"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], name="fk_cocoons_owner_user_id_users"),
    )

    sa.Table(
        "cocoon_tag_bindings",
        metadata,
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("cocoon_id", sa.String(length=64), nullable=False),
        sa.Column("tag_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["cocoon_id"], ["cocoons.id"], name="fk_cocoon_tag_bindings_cocoon_id_cocoons"),
        sa.PrimaryKeyConstraint("id", name="pk_cocoon_tag_bindings"),
    )

    sa.Table(
        "session_states",
        metadata,
        sa.Column("cocoon_id", sa.String(length=64), nullable=False),
        sa.Column("relation_score", sa.Integer(), nullable=False),
        sa.Column("persona_json", sa.JSON(), nullable=False),
        sa.Column("active_tags_json", sa.JSON(), nullable=False),
        sa.Column("current_wakeup_task_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("cocoon_id", name="pk_session_states"),
        sa.ForeignKeyConstraint(
            ["current_wakeup_task_id"], ["wakeup_tasks.id"], name="fk_session_states_current_wakeup_task_id_wakeup_tasks"
        ),
        sa.ForeignKeyConstraint(["cocoon_id"], ["cocoons.id"], name="fk_session_states_cocoon_id_cocoons"),
    )

    sa.Table(
        "messages",
        metadata,
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("cocoon_id", sa.String(length=64), nullable=False),
        sa.Column("action_id", sa.String(length=64), nullable=True),
        sa.Column("client_request_id", sa.String(length=128), nullable=True),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_thought", sa.Boolean(), nullable=False),
        sa.Column("tags_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["cocoon_id"], ["cocoons.id"], name="fk_messages_cocoon_id_cocoons"),
        sa.PrimaryKeyConstraint("id", name="pk_messages"),
        sa.UniqueConstraint("client_request_id", name="uq_messages_client_request_id"),
        sa.ForeignKeyConstraint(["action_id"], ["action_dispatches.id"], name="fk_messages_action_id_action_dispatches", use_alter=True),
    )

    sa.Table(
        "message_tags",
        metadata,
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("message_id", sa.String(length=64), nullable=False),
        sa.Column("tag_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], name="fk_message_tags_message_id_messages"),
        sa.PrimaryKeyConstraint("id", name="pk_message_tags"),
    )

    sa.Table(
        "memory_chunks",
        metadata,
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("cocoon_id", sa.String(length=64), nullable=False),
        sa.Column("source_message_id", sa.String(length=64), nullable=True),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("tags_json", sa.JSON(), nullable=False),
        sa.Column("meta_json", sa.JSON(), nullable=False),
        sa.Column("embedding_ref", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_memory_chunks"),
        sa.ForeignKeyConstraint(["source_message_id"], ["messages.id"], name="fk_memory_chunks_source_message_id_messages"),
        sa.ForeignKeyConstraint(["cocoon_id"], ["cocoons.id"], name="fk_memory_chunks_cocoon_id_cocoons"),
    )

    sa.Table(
        "memory_tags",
        metadata,
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("memory_chunk_id", sa.String(length=64), nullable=False),
        sa.Column("tag_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["memory_chunk_id"], ["memory_chunks.id"], name="fk_memory_tags_memory_chunk_id_memory_chunks"),
        sa.PrimaryKeyConstraint("id", name="pk_memory_tags"),
    )

    sa.Table(
        "failed_rounds",
        metadata,
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("cocoon_id", sa.String(length=64), nullable=False),
        sa.Column("action_id", sa.String(length=64), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_failed_rounds"),
        sa.ForeignKeyConstraint(["action_id"], ["action_dispatches.id"], name="fk_failed_rounds_action_id_action_dispatches"),
        sa.ForeignKeyConstraint(["cocoon_id"], ["cocoons.id"], name="fk_failed_rounds_cocoon_id_cocoons"),
    )

    return metadata


def upgrade() -> None:
    build_metadata().create_all(op.get_bind())


def downgrade() -> None:
    build_metadata().drop_all(op.get_bind())
