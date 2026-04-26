from datetime import datetime

import pytest
from fastapi import HTTPException

from app.models import Message
from app.services.workspace.message_service import MessageService
from tests.sqlite_helpers import make_sqlite_session_factory


def _session_factory():
    return make_sqlite_session_factory()


def test_message_service_lists_serializes_and_retracts_messages():
    session_factory = _session_factory()
    service = MessageService()

    with session_factory() as session:
        first = Message(
            id="msg-1",
            cocoon_id="cocoon-1",
            role="user",
            content="hello",
            external_sender_id="peer-1",
            external_sender_display_name="Alice",
            created_at=datetime(2026, 4, 22, 10, 0, 0),
        )
        second = Message(
            id="msg-2",
            cocoon_id="cocoon-1",
            role="assistant",
            content="reply",
            is_retracted=True,
            created_at=datetime(2026, 4, 22, 10, 1, 0),
        )
        session.add_all([first, second])
        session.commit()

        listed = service.list_messages(session, cocoon_id="cocoon-1")
        latest = service.list_messages(session, cocoon_id="cocoon-1", limit=1)
        older_than_second = service.list_messages(
            session,
            cocoon_id="cocoon-1",
            before_message_id="msg-2",
            limit=1,
        )
        serialized = service.serialize_message(second)
        serialized_first = service.serialize_message(first)
        retracted = service.retract_message(session, first, acting_user_id="user-1", note=None)
        unchanged = service.retract_message(session, retracted, acting_user_id="user-2", note="ignored")

        assert [message.id for message in listed] == ["msg-1", "msg-2"]
        assert [message.id for message in latest] == ["msg-2"]
        assert [message.id for message in older_than_second] == ["msg-1"]
        assert serialized.content == MessageService.RETRACTED_PLACEHOLDER
        assert serialized_first.external_sender_id == "peer-1"
        assert serialized_first.external_sender_display_name == "Alice"
        assert retracted.is_retracted is True
        assert retracted.retraction_note == "Message retracted"
        assert retracted.retracted_by_user_id == "user-1"
        assert retracted.retracted_at is not None
        assert unchanged.retracted_by_user_id == "user-1"


def test_message_service_requires_message_for_target():
    session_factory = _session_factory()
    service = MessageService()

    with session_factory() as session:
        cocoon_message = Message(id="msg-1", cocoon_id="cocoon-1", role="user", content="hello")
        chat_group_message = Message(id="msg-2", chat_group_id="group-1", role="user", content="group")
        session.add_all([cocoon_message, chat_group_message])
        session.commit()

        assert service.require_message_for_target(session, "msg-1", cocoon_id="cocoon-1").id == "msg-1"
        assert service.require_message_for_target(session, "msg-2", chat_group_id="group-1").id == "msg-2"

        with pytest.raises(HTTPException) as missing:
            service.require_message_for_target(session, "missing", cocoon_id="cocoon-1")
        assert missing.value.status_code == 404

        with pytest.raises(HTTPException) as wrong_cocoon:
            service.require_message_for_target(session, "msg-1", cocoon_id="other")
        assert wrong_cocoon.value.status_code == 404

        with pytest.raises(HTTPException) as wrong_group:
            service.require_message_for_target(session, "msg-2", chat_group_id="other")
        assert wrong_group.value.status_code == 404
