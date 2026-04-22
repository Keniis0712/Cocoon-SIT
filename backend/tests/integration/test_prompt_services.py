import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models import PromptTemplate, PromptTemplateRevision, PromptVariable
from app.services.prompts.prompt_render_service import PromptRenderService
from app.services.prompts.prompt_revision_service import PromptRevisionService
from app.services.prompts.prompt_variable_service import PromptVariableService

pytestmark = pytest.mark.integration


def test_prompt_variable_service_syncs_registered_variables(client):
    container = client.app.state.container
    service = PromptVariableService()

    with container.session_factory() as session:
        session.query(PromptVariable).delete()
        session.commit()

    with container.session_factory() as session:
        service.sync_registry_defaults(session)
        session.commit()
        variables = list(session.scalars(select(PromptVariable)).all())
        assert variables
        assert any(
            item.template_type == "generator" and item.variable_name == "visible_messages"
            for item in variables
        )


def test_prompt_revision_service_creates_revision_history(client):
    container = client.app.state.container
    service = PromptRevisionService()

    with container.session_factory() as session:
        template = service.upsert_template(
            session,
            template_type="generator",
            name="Generator One",
            description="first",
            content="Reply with {{ visible_messages }}",
            actor_user_id=None,
        )
        service.upsert_template(
            session,
            template_type="generator",
            name="Generator Two",
            description="second",
            content="Reply using {{ visible_messages }} and {{ runtime_event }}",
            actor_user_id=None,
        )
        session.commit()

        revisions = list(
            session.scalars(
                select(PromptTemplateRevision).where(PromptTemplateRevision.template_id == template.id)
            ).all()
        )
        persisted = session.scalar(
            select(PromptTemplate).where(PromptTemplate.template_type == "generator")
        )
        assert persisted is not None
        assert persisted.name == "Generator Two"
        assert len(revisions) >= 2


def test_prompt_render_service_uses_active_revision(client):
    container = client.app.state.container
    revision_service = PromptRevisionService()
    render_service = PromptRenderService(revision_service)

    with container.session_factory() as session:
        revision_service.upsert_template(
            session,
            template_type="merge",
            name="Merge Render",
            description="render test",
            content="Merge {{ runtime_event }} into {{ merge_context }}",
            actor_user_id=None,
        )
        session.commit()

    with container.session_factory() as session:
        _, revision, snapshot, rendered = render_service.render(
            session,
            "merge",
            {"runtime_event": {"type": "merge"}, "merge_context": {"source": "one"}},
        )
        assert set(revision.variables_json) == {"runtime_event", "merge_context"}
        assert "merge_context" in snapshot
        assert "source" in rendered


def test_prompt_render_service_rejects_missing_variables(client):
    container = client.app.state.container
    render_service = container.prompt_service.prompt_render_service

    with container.session_factory() as session:
        with pytest.raises(HTTPException) as exc_info:
            render_service.render(session, "generator", {"visible_messages": []})
        assert exc_info.value.status_code == 422
        assert "Missing prompt variables" in str(exc_info.value.detail)
