from app.core.container import AppContainer
from app.models import Base, Role as RootRole
from app.models.entities import PromptTemplateType, Role as CompatRole, new_id, utcnow


def test_model_compatibility_exports_preserve_existing_imports():
    assert RootRole is CompatRole
    assert PromptTemplateType.generator == "generator"
    assert isinstance(new_id(), str)
    assert utcnow().tzinfo is None
    assert "roles" in Base.metadata.tables
    assert "audit_runs" in Base.metadata.tables
    assert "prompt_templates" in Base.metadata.tables


def test_app_container_wires_domain_services(test_settings):
    settings = test_settings.model_copy(update={"auto_seed_defaults": False})
    container = AppContainer(settings)

    try:
        assert container.chat_queue is not None
        assert container.realtime_hub is not None
        assert container.auth_session_service is not None
        assert container.prompt_service is not None
        assert container.bootstrap_service is not None
        assert container.audit_service is not None
        assert container.provider_registry is not None
        assert container.message_dispatch_service is not None
        assert container.chat_runtime is not None
        assert container.scheduler_node is not None
    finally:
        container.shutdown()
