from __future__ import annotations

from app.services.access.auth_session_service import AuthSessionService
from app.services.access.group_service import GroupService
from app.services.access.invite_service import InviteService
from app.services.access.role_service import RoleService
from app.services.access.user_service import UserService
from app.services.audit.service import AuditService
from app.services.bootstrap_service import BootstrapService
from app.services.catalog.character_service import CharacterService
from app.services.catalog.embedding_provider_service import EmbeddingProviderService
from app.services.catalog.model_catalog_service import ModelCatalogService
from app.services.catalog.prompt_template_admin_service import PromptTemplateAdminService
from app.services.catalog.provider_credential_service import ProviderCredentialService
from app.services.catalog.provider_service import ProviderService
from app.services.catalog.tag_service import TagService
from app.services.catalog.system_settings_service import SystemSettingsService
from app.services.memory.service import MemoryService
from app.services.observability.artifact_admin_service import ArtifactAdminService
from app.services.observability.audit_query_service import AuditQueryService
from app.services.observability.insight_query_service import InsightQueryService
from app.services.prompts.service import PromptTemplateService
from app.services.providers.model_selection_service import ModelSelectionService
from app.services.providers.provider_factory import ProviderFactory
from app.services.providers.provider_runtime_config_service import ProviderRuntimeConfigService
from app.services.providers.registry import ProviderRegistry
from app.services.realtime.connection_manager import ConnectionManager
from app.services.realtime.event_delivery_service import EventDeliveryService
from app.services.realtime.hub import RealtimeHub
from app.services.runtime.chat_runtime import ChatRuntime
from app.services.runtime.context.external_context_service import ExternalContextService
from app.services.runtime.context.message_window_service import MessageWindowService
from app.services.runtime.context_builder import ContextBuilder
from app.services.runtime.generation.prompt_assembly_service import PromptAssemblyService
from app.services.runtime.generator_node import GeneratorNode
from app.services.runtime.meta_node import MetaNode
from app.services.runtime.reply_delivery_service import ReplyDeliveryService
from app.services.runtime.round_preparation_service import RoundPreparationService
from app.services.runtime.round_cleanup import RoundCleanupService
from app.services.runtime.scheduler_node import SchedulerNode
from app.services.runtime.side_effects import SideEffects
from app.services.runtime.state_patch_service import StatePatchService
from app.services.security.encryption import SecretCipher
from app.services.security.authorization_service import AuthorizationService
from app.services.security.token_authentication_service import TokenAuthenticationService
from app.services.security.token_service import TokenService
from app.services.storage.filesystem import FilesystemArtifactStore
from app.services.workspace.cocoon_tag_service import CocoonTagService
from app.services.workspace.cocoon_tree_service import CocoonTreeService
from app.services.workspace.chat_group_service import ChatGroupService
from app.services.workspace.message_dispatch_service import MessageDispatchService
from app.services.workspace.message_service import MessageService
from app.services.workspace.workspace_realtime_service import WorkspaceRealtimeService
from app.services.jobs.durable_jobs import DurableJobService


def wire_infrastructure_services(container) -> None:
    container.connection_manager = ConnectionManager()
    container.backplane = container._build_backplane()
    container.event_delivery_service = EventDeliveryService()
    container.realtime_hub = RealtimeHub(
        container.connection_manager,
        container.backplane,
        delivery_service=container.event_delivery_service,
    )
    container.chat_queue = container._build_chat_queue()


def wire_security_services(container) -> None:
    container.secret_cipher = SecretCipher(container.settings.provider_master_key)
    container.authorization_service = AuthorizationService()
    container.token_service = TokenService(container.settings)
    container.token_authentication_service = TokenAuthenticationService(container.token_service)


def wire_access_services(container) -> None:
    container.system_settings_service = SystemSettingsService(container.settings)
    container.auth_session_service = AuthSessionService(
        container.token_service,
        container.settings,
        system_settings_service=container.system_settings_service,
    )
    container.user_service = UserService()
    container.role_service = RoleService()
    container.group_service = GroupService()
    container.invite_service = InviteService()


def wire_prompt_and_audit_services(container) -> None:
    container.artifact_store = FilesystemArtifactStore(container.settings.artifact_root)
    container.prompt_service = PromptTemplateService()
    container.bootstrap_service = BootstrapService(container.settings, container.prompt_service)
    container.audit_service = AuditService(container.artifact_store, container.settings)


def wire_provider_and_catalog_services(container) -> None:
    container.model_selection_service = ModelSelectionService()
    container.provider_runtime_config_service = ProviderRuntimeConfigService(container.secret_cipher)
    container.provider_factory = ProviderFactory()
    container.provider_registry = ProviderRegistry(
        container.model_selection_service,
        container.provider_runtime_config_service,
        container.provider_factory,
    )
    container.memory_service = MemoryService(container.provider_registry)
    container.provider_service = ProviderService(
        container.provider_runtime_config_service,
        container.provider_factory,
    )
    container.provider_credential_service = ProviderCredentialService(container.secret_cipher)
    container.model_catalog_service = ModelCatalogService()
    container.embedding_provider_service = EmbeddingProviderService(container.secret_cipher)
    container.character_service = CharacterService()
    container.prompt_template_admin_service = PromptTemplateAdminService(container.prompt_service)
    container.tag_service = TagService()


def wire_workspace_services(container) -> None:
    container.cocoon_tree_service = CocoonTreeService()
    container.chat_group_service = ChatGroupService(container.system_settings_service)
    container.message_dispatch_service = MessageDispatchService(
        container.chat_queue,
        container.realtime_hub,
        system_settings_service=container.system_settings_service,
    )
    container.message_service = MessageService()
    container.cocoon_tag_service = CocoonTagService()
    container.workspace_realtime_service = WorkspaceRealtimeService(
        container.session_factory,
        container.token_authentication_service,
        container.authorization_service,
        container.connection_manager,
    )
    container.durable_jobs = DurableJobService()


def wire_observability_services(container) -> None:
    container.audit_query_service = AuditQueryService(
        container.authorization_service,
        container.artifact_store,
    )
    container.artifact_admin_service = ArtifactAdminService(container.artifact_store)
    container.insight_query_service = InsightQueryService(container.authorization_service)


def wire_runtime_services(container) -> None:
    container.round_cleanup = RoundCleanupService()
    container.scheduler_node = SchedulerNode(container.durable_jobs)
    container.message_window_service = MessageWindowService()
    container.external_context_service = ExternalContextService(
        memory_service=container.memory_service,
        message_window_service=container.message_window_service,
    )
    container.prompt_assembly_service = PromptAssemblyService(container.prompt_service)
    container.side_effects = SideEffects(container.audit_service, container.memory_service)
    container.round_preparation_service = RoundPreparationService(
        audit_service=container.audit_service,
        round_cleanup=container.round_cleanup,
    )
    container.state_patch_service = StatePatchService(
        side_effects=container.side_effects,
        realtime_hub=container.realtime_hub,
    )
    container.reply_delivery_service = ReplyDeliveryService(
        side_effects=container.side_effects,
        audit_service=container.audit_service,
        realtime_hub=container.realtime_hub,
    )
    container.chat_runtime = ChatRuntime(
        context_builder=ContextBuilder(
            container.memory_service,
            message_window_service=container.message_window_service,
            external_context_service=container.external_context_service,
        ),
        meta_node=MetaNode(
            prompt_service=container.prompt_service,
            audit_service=container.audit_service,
            provider_registry=container.provider_registry,
        ),
        generator_node=GeneratorNode(
            prompt_assembly_service=container.prompt_assembly_service,
            provider_registry=container.provider_registry,
            audit_service=container.audit_service,
        ),
        scheduler_node=container.scheduler_node,
        round_preparation_service=container.round_preparation_service,
        state_patch_service=container.state_patch_service,
        reply_delivery_service=container.reply_delivery_service,
        side_effects=container.side_effects,
        audit_service=container.audit_service,
    )
