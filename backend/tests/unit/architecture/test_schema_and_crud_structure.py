from pathlib import Path

from app.crud.catalog.prompts import list_prompt_templates
from app.crud.catalog.providers import list_model_providers
from app.crud.jobs.durable_jobs import enqueue_durable_job
from app.crud.workspace.action_dispatch import get_action_by_client_request_id
from app.crud.workspace.cocoons import get_session_state, list_cocoons, list_messages
from app.schemas.access.auth import LoginRequest, RoleCreate, UserCreate
from app.schemas.catalog.characters import CharacterCreate
from app.schemas.catalog.embedding_providers import EmbeddingProviderCreate
from app.schemas.catalog.models import AvailableModelCreate
from app.schemas.catalog.prompts import PromptTemplateUpsertRequest
from app.schemas.catalog.providers import ModelProviderCreate, ProviderCredentialCreate
from app.schemas.catalog.tags import TagCreate
from app.schemas.observability.artifacts import ArtifactCleanupRequest
from app.schemas.observability.audits import AuditArtifactOut
from app.schemas.observability.insights import InsightMetric
from app.schemas.realtime.events import ReplyDoneEvent
from app.schemas.workspace.checkpoints import CheckpointOut
from app.schemas.workspace.cocoons import ChatMessageCreate, CocoonCreate
from app.schemas.workspace.jobs import DurableJobOut


def test_schema_modules_import_from_domain_packages():
    assert LoginRequest.model_fields["username"] is not None
    assert UserCreate.model_fields["password"] is not None
    assert RoleCreate.model_fields["permissions_json"] is not None
    assert CharacterCreate.model_fields["settings_json"] is not None
    assert ModelProviderCreate.model_fields["capabilities_json"] is not None
    assert ProviderCredentialCreate.model_fields["secret"] is not None
    assert AvailableModelCreate.model_fields["provider_id"] is not None
    assert EmbeddingProviderCreate.model_fields["model_name"] is not None
    assert PromptTemplateUpsertRequest.model_fields["content"] is not None
    assert TagCreate.model_fields["tag_id"] is not None
    assert CocoonCreate.model_fields["character_id"] is not None
    assert ChatMessageCreate.model_fields["client_request_id"] is not None
    assert CheckpointOut.model_fields["anchor_message_id"] is not None
    assert DurableJobOut.model_fields["job_type"] is not None
    assert AuditArtifactOut.model_fields["kind"] is not None
    assert ArtifactCleanupRequest.model_fields["artifact_ids"] is not None
    assert InsightMetric.model_fields["name"] is not None
    assert ReplyDoneEvent.model_fields["final_message_id"] is not None


def test_crud_modules_import_from_domain_packages():
    assert callable(list_prompt_templates)
    assert callable(list_model_providers)
    assert callable(enqueue_durable_job)
    assert callable(get_action_by_client_request_id)
    assert callable(list_cocoons)
    assert callable(list_messages)
    assert callable(get_session_state)


def test_flat_schema_and_crud_files_are_removed():
    root = Path.cwd() / "backend" / "app"
    removed_schema_files = [
        "schemas/auth.py",
        "schemas/grouping.py",
        "schemas/invite.py",
        "schemas/character.py",
        "schemas/prompt.py",
        "schemas/provider.py",
        "schemas/provider_admin.py",
        "schemas/tagging.py",
        "schemas/cocoon.py",
        "schemas/checkpoints.py",
        "schemas/jobs.py",
        "schemas/audit.py",
        "schemas/artifacts.py",
        "schemas/insights.py",
        "schemas/ws.py",
    ]
    removed_crud_files = [
        "crud/action_dispatch.py",
        "crud/cocoons.py",
        "crud/durable_jobs.py",
        "crud/prompts.py",
        "crud/providers.py",
    ]

    for relative_path in [*removed_schema_files, *removed_crud_files]:
        assert not (root / relative_path).exists(), relative_path
