from sqlalchemy import select
import pytest

from app.models import Character, ModelProvider, TagRegistry, User
from app.schemas.catalog.characters import CharacterAclCreate, CharacterCreate, CharacterUpdate
from app.schemas.catalog.prompts import PromptTemplateUpsertRequest
from app.schemas.catalog.tags import TagCreate, TagUpdate

pytestmark = pytest.mark.integration


def test_character_service_and_acl(client):
    container = client.app.state.container
    with container.session_factory() as session:
        admin = session.scalars(select(User).where(User.username == "admin")).first()
        character = container.character_service.create_character(
            session,
            CharacterCreate(name="Svc Character", prompt_summary="helper", settings_json={"tone": "calm"}),
            admin,
        )
        acl = container.character_service.create_acl(
            session,
            character.id,
            CharacterAclCreate(
                subject_type="user",
                subject_id=admin.id,
                can_read=True,
                can_use=True,
            ),
        )
        session.commit()
        character_id = character.id
        assert acl.character_id == character.id

    with container.session_factory() as session:
        updated = container.character_service.update_character(
            session,
            character_id,
            CharacterUpdate(prompt_summary="updated helper"),
        )
        session.commit()
        assert updated.prompt_summary == "updated helper"
        assert any(item.id == character_id for item in container.character_service.list_characters(session))
        assert container.character_service.list_acl(session, character_id)


def test_prompt_template_admin_and_tag_services(client):
    container = client.app.state.container
    with container.session_factory() as session:
        admin = session.scalars(select(User).where(User.username == "admin")).first()
        template = container.prompt_template_admin_service.upsert_template(
            session,
            "generator",
            PromptTemplateUpsertRequest(
                name="Svc Generator",
                description="service level",
                content="Reply with {{ visible_messages }}",
            ),
            admin,
        )
        tag = container.tag_service.create_tag(
            session,
            TagCreate(tag_id="svc-tag", brief="Service tag", is_isolated=False, meta_json={"color": "green"}),
        )
        session.commit()
        assert template.template_type == "generator"
        assert tag.tag_id == "svc-tag"

    with container.session_factory() as session:
        updated = container.tag_service.update_tag(
            session,
            "svc-tag",
            TagUpdate(brief="Updated service tag", is_isolated=True),
        )
        session.commit()
        assert updated.brief == "Updated service tag"
        assert any(item.tag_id == "svc-tag" for item in container.tag_service.list_tags(session))
        templates = container.prompt_template_admin_service.list_templates(session)
        assert any(item.template_type == "generator" for item in templates)
