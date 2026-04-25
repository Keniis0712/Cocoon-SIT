import pytest
from fastapi import HTTPException

from app.models import Cocoon, CocoonTagBinding, MemoryChunk, MemoryTag, Message, MessageTag, SessionState, User
from app.schemas.catalog.tags import TagCreate, TagUpdate
from app.services.catalog.tag_policy import ensure_user_system_tag
from app.services.catalog.tag_service import TagService
from tests.sqlite_helpers import make_sqlite_session_factory


def _session_factory():
    return make_sqlite_session_factory()


def test_tag_service_lists_creates_updates_and_deletes_tags():
    session_factory = _session_factory()
    service = TagService()

    with session_factory() as session:
        user = User(username="owner", email="owner@example.com", password_hash="hash")
        session.add(user)
        session.flush()
        ensure_user_system_tag(session, user.id)
        session.add(Cocoon(id="cocoon-1", name="Test", owner_user_id=user.id, character_id="character-1", selected_model_id="model-1"))
        session.flush()
        created = service.create_tag(
            session,
            user,
            TagCreate(tag_id="focus", brief="Focus tag", visibility="private", is_isolated=False, meta_json={"kind": "a"}),
        )
        private = service.create_tag(
            session,
            user,
            TagCreate(tag_id="private-tag", brief="Private tag", visibility="private", meta_json={}),
        )
        listed = service.list_tags(session, user)
        updated = service.update_tag(
            session,
            user,
            "focus",
            TagUpdate(brief="Updated", visibility="private", meta_json={"kind": "b"}),
        )

        session.add_all(
            [
                CocoonTagBinding(cocoon_id="cocoon-1", tag_id=updated.id),
                MessageTag(message_id="message-1", tag_id=updated.id),
                MemoryTag(memory_chunk_id="memory-1", tag_id=updated.id),
                SessionState(cocoon_id="cocoon-1", persona_json={}, active_tags_json=[updated.id, private.id]),
                Message(id="message-1", cocoon_id="cocoon-1", role="user", content="hello", tags_json=[updated.id, private.id]),
                MemoryChunk(
                    id="memory-1",
                    cocoon_id="cocoon-1",
                    owner_user_id="user-1",
                    character_id="character-1",
                    scope="session",
                    content="memory",
                    tags_json=[updated.id, private.id],
                ),
            ]
        )
        session.flush()

        deleted = service.delete_tag(session, user, updated.id)
        state = session.get(SessionState, "cocoon-1")
        message = session.get(Message, "message-1")
        memory = session.get(MemoryChunk, "memory-1")

        assert [tag.tag_id for tag in listed] == ["default", "focus", "private-tag"]
        assert private.is_isolated is True
        assert updated.brief == "Updated"
        assert updated.visibility == "private"
        assert updated.is_isolated is True
        assert updated.meta_json == {"kind": "b"}
        assert deleted.id == updated.id
        assert state is not None and private.id in state.active_tags_json and len(state.active_tags_json) == 2
        assert message is not None and message.tags_json == [private.id]
        assert memory is not None and memory.tags_json == [private.id]
        assert session.get(type(created), created.id) is None


def test_tag_service_validates_missing_tags_and_isolation_override():
    session_factory = _session_factory()
    service = TagService()

    with session_factory() as session:
        user = User(username="owner", email="owner@example.com", password_hash="hash")
        session.add(user)
        session.flush()
        ensure_user_system_tag(session, user.id)
        created = service.create_tag(
            session,
            user,
            TagCreate(tag_id="open", brief="Open tag", visibility="private", is_isolated=False, meta_json={}),
        )
        updated = service.update_tag(session, user, created.id, TagUpdate(visibility="private", is_isolated=True))
        assert updated.is_isolated is True

        with pytest.raises(HTTPException) as missing_update:
            service.update_tag(session, user, "missing", TagUpdate(brief="none"))
        assert missing_update.value.status_code == 404

        with pytest.raises(HTTPException) as missing_delete:
            service.delete_tag(session, user, "missing")
        assert missing_delete.value.status_code == 404

        with pytest.raises(HTTPException) as unsupported_visibility:
            service.update_tag(session, user, created.id, TagUpdate(visibility="public"))
        assert unsupported_visibility.value.status_code == 400
