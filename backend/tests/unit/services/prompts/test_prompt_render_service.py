import pytest
from fastapi import HTTPException

from app.models import PromptTemplate, PromptTemplateRevision
from app.services.prompts.prompt_render_service import PromptRenderService


def test_render_returns_template_revision_snapshot_and_rendered_text(monkeypatch):
    template = PromptTemplate(template_type="system", name="System")
    revision = PromptTemplateRevision(
        template_id=template.id,
        version=1,
        content="Hello {{name}}",
        variables_json=["name", "token"],
        checksum="checksum",
    )
    revision_service = type(
        "_RevisionService",
        (),
        {
            "get_template": lambda self, session, template_type: template,
            "get_active_revision": lambda self, session, template_obj: revision,
        },
    )()

    monkeypatch.setattr(
        "app.services.prompts.prompt_render_service.sanitize_snapshot",
        lambda value: {"name": value["name"], "token": "***redacted***"},
    )
    monkeypatch.setattr(
        "app.services.prompts.prompt_render_service.render_template",
        lambda content, snapshot: f"{content} => {snapshot['name']}/{snapshot['token']}",
    )

    result = PromptRenderService(revision_service).render(
        session=object(),
        template_type="system",
        variables={"name": "Ada", "token": "secret"},
    )

    assert result == (
        template,
        revision,
        {"name": "Ada", "token": "***redacted***"},
        "Hello {{name}} => Ada/***redacted***",
    )


def test_render_raises_when_no_active_revision():
    template = PromptTemplate(template_type="system", name="System")
    revision_service = type(
        "_RevisionService",
        (),
        {
            "get_template": lambda self, session, template_type: template,
            "get_active_revision": lambda self, session, template_obj: None,
        },
    )()

    with pytest.raises(HTTPException) as exc:
        PromptRenderService(revision_service).render(
            session=object(),
            template_type="system",
            variables={},
        )

    assert exc.value.status_code == 500
    assert exc.value.detail == "No active revision"


def test_render_raises_when_required_variables_are_missing():
    template = PromptTemplate(template_type="system", name="System")
    revision = PromptTemplateRevision(
        template_id=template.id,
        version=1,
        content="Hello {{name}}",
        variables_json=["name", "location"],
        checksum="checksum",
    )
    revision_service = type(
        "_RevisionService",
        (),
        {
            "get_template": lambda self, session, template_type: template,
            "get_active_revision": lambda self, session, template_obj: revision,
        },
    )()

    with pytest.raises(HTTPException) as exc:
        PromptRenderService(revision_service).render(
            session=object(),
            template_type="system",
            variables={"name": "Ada"},
        )

    assert exc.value.status_code == 422
    assert "location" in exc.value.detail
