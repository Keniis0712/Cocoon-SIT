from app.models import PromptTemplate
from app.services.prompts.prompt_render_service import PromptRenderService
from app.services.prompts.prompt_revision_service import PromptRevisionService
from app.services.prompts.prompt_variable_service import PromptVariableService
from app.services.prompts.service import PromptTemplateService


class _FakeVariableService:
    def __init__(self):
        self.calls = []

    def sync_registry_defaults(self, session):
        self.calls.append(("sync_registry_defaults", session))


class _FakeRevisionService:
    def __init__(self):
        self.calls = []
        self.template = PromptTemplate(template_type="system", name="System")

    def ensure_default_templates(self, session):
        self.calls.append(("ensure_default_templates", session))

    def list_templates(self, session):
        self.calls.append(("list_templates", session))
        return [self.template]

    def get_template(self, session, template_type):
        self.calls.append(("get_template", session, template_type))
        return self.template

    def get_active_revision(self, session, template):
        self.calls.append(("get_active_revision", session, template))
        return "revision"

    def upsert_template(self, **kwargs):
        self.calls.append(("upsert_template", kwargs))
        return self.template

    def reset_template(self, **kwargs):
        self.calls.append(("reset_template", kwargs))
        return self.template


class _FakeRenderService:
    def __init__(self):
        self.calls = []

    def render(self, session, template_type, variables):
        self.calls.append((session, template_type, variables))
        return ("template", "revision", {"x": 1}, "rendered")


def test_service_constructor_builds_default_subservices():
    service = PromptTemplateService()

    assert isinstance(service.prompt_variable_service, PromptVariableService)
    assert isinstance(service.prompt_revision_service, PromptRevisionService)
    assert isinstance(service.prompt_render_service, PromptRenderService)
    assert service.prompt_render_service.prompt_revision_service is service.prompt_revision_service


def test_service_delegates_all_operations_to_subservices():
    variable_service = _FakeVariableService()
    revision_service = _FakeRevisionService()
    render_service = _FakeRenderService()
    service = PromptTemplateService(
        prompt_variable_service=variable_service,
        prompt_revision_service=revision_service,
        prompt_render_service=render_service,
    )
    session = object()

    service.ensure_defaults(session)
    assert service.list_templates(session) == [revision_service.template]
    assert service.get_template(session, "system") is revision_service.template
    assert service.get_active_revision(session, revision_service.template) == "revision"
    assert service.upsert_template(session, "system", "System", "Desc", "Hello", "user-1") is revision_service.template
    assert service.reset_template(session, "system", "user-1") is revision_service.template
    assert service.render(session, "system", {"name": "Ada"}) == ("template", "revision", {"x": 1}, "rendered")

    assert variable_service.calls == [("sync_registry_defaults", session)]
    assert ("ensure_default_templates", session) in revision_service.calls
    assert ("list_templates", session) in revision_service.calls
    assert ("get_template", session, "system") in revision_service.calls
    assert render_service.calls == [(session, "system", {"name": "Ada"})]
