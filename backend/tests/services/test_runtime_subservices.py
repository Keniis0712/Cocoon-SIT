from sqlalchemy import select

from app.models import Character, Cocoon, MemoryChunk, Message, SessionState
from app.services.runtime.context.external_context_service import ExternalContextService
from app.services.runtime.context.message_window_service import MessageWindowService
from app.services.runtime.generation.prompt_assembly_service import PromptAssemblyService
from app.services.runtime.types import ContextPackage, RuntimeEvent


def test_message_window_service_filters_by_active_tags(client, default_cocoon_id):
    container = client.app.state.container
    service = MessageWindowService()
    with container.session_factory() as session:
        session.add_all(
            [
                Message(cocoon_id=default_cocoon_id, role="user", content="Visible", tags_json=["focus"]),
                Message(cocoon_id=default_cocoon_id, role="user", content="Hidden", tags_json=["other"]),
            ]
        )
        session.commit()

    with container.session_factory() as session:
        messages = service.list_visible_messages(
            session=session,
            cocoon_id=default_cocoon_id,
            max_context_messages=10,
            active_tags=["focus"],
        )
        contents = [message.content for message in messages]
        assert "Visible" in contents
        assert "Hidden" not in contents


def test_external_context_service_builds_merge_context(client, auth_headers, default_cocoon_id, create_branch_cocoon):
    container = client.app.state.container
    source_cocoon_id = create_branch_cocoon("Source Context")["id"]

    with container.session_factory() as session:
        state = session.get(SessionState, source_cocoon_id) or SessionState(cocoon_id=source_cocoon_id)
        session.add(state)
        state.active_tags_json = ["mergeable"]
        session.add(Message(cocoon_id=source_cocoon_id, role="user", content="Source message"))
        session.add(MemoryChunk(cocoon_id=source_cocoon_id, scope="dialogue", content="Source memory"))
        session.commit()

    service = ExternalContextService(
        memory_service=container.memory_service,
        message_window_service=container.message_window_service,
    )
    with container.session_factory() as session:
        context = service.build(
            session,
            RuntimeEvent(
                event_type="merge",
                cocoon_id=default_cocoon_id,
                chat_group_id=None,
                action_id="action-1",
                payload={"source_cocoon_id": source_cocoon_id},
            ),
        )
        assert context["source_cocoon"].id == source_cocoon_id
        assert context["merge_context"]["source_cocoon"]["name"] == "Source Context"
        assert context["source_messages"][0].content == "Source message"


def test_prompt_assembly_service_uses_merge_template(client, auth_headers, default_cocoon_id):
    container = client.app.state.container
    prompt_service = PromptAssemblyService(container.prompt_service)
    with container.session_factory() as session:
        cocoon = session.get(Cocoon, default_cocoon_id)
        character = session.get(Character, cocoon.character_id)
        state = session.get(SessionState, default_cocoon_id)
        state.active_tags_json = []
        session.add(Message(cocoon_id=default_cocoon_id, role="user", content="Target message"))
        session.commit()
        visible_messages = list(
            session.scalars(
                select(Message).where(Message.cocoon_id == default_cocoon_id).order_by(Message.created_at.asc())
            ).all()
        )
        context = ContextPackage(
            runtime_event=RuntimeEvent(
                event_type="merge",
                cocoon_id=default_cocoon_id,
                chat_group_id=None,
                action_id="merge-action",
                payload={"source_cocoon_id": "source-1"},
            ),
            conversation=cocoon,
            character=character,
            session_state=state,
            visible_messages=visible_messages,
            memory_context=[],
            external_context={
                "merge_context": {"source_cocoon": {"id": "source-1", "name": "Source"}},
                "source_messages": visible_messages,
            },
        )

        assembly = prompt_service.build(
            session=session,
            context=context,
            provider_capabilities={"streaming": True},
        )

    assert assembly.event.summary_prefix == "merge"
    assert any(message["content"] == "Target message" for message in assembly.messages)
    assert assembly.combined_prompt
