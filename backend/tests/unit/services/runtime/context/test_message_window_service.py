from datetime import UTC, datetime, timedelta

from app.models import Cocoon
from app.models import Message
from app.services.runtime.context.message_window_service import MessageWindowService
from tests.sqlite_helpers import make_sqlite_session_factory


def test_message_window_service_respects_context_start_message_id_for_cocoons():
    session_factory = make_sqlite_session_factory()
    service = MessageWindowService()
    base_time = datetime.now(UTC).replace(tzinfo=None)

    with session_factory() as session:
        messages = []
        for index in range(1, 8):
            message = Message(
                id=f"m{index}",
                cocoon_id="cocoon-1",
                role="user",
                content=f"message-{index}",
                created_at=base_time + timedelta(seconds=index),
                updated_at=base_time + timedelta(seconds=index),
            )
            session.add(message)
            messages.append(message)
        session.commit()

        visible = service.list_visible_messages(
            session,
            5,
            [],
            cocoon_id="cocoon-1",
            context_start_message_id="m5",
        )

        assert [message.id for message in visible] == ["m5", "m6", "m7"]

        fallback = service.list_visible_messages(
            session,
            5,
            [],
            cocoon_id="cocoon-1",
            context_start_message_id="missing",
        )

        assert [message.id for message in fallback] == ["m3", "m4", "m5", "m6", "m7"]


def test_message_window_service_includes_parent_chain_messages_for_child_cocoons():
    session_factory = make_sqlite_session_factory()
    service = MessageWindowService()
    base_time = datetime.now(UTC).replace(tzinfo=None)

    with session_factory() as session:
        session.add_all(
            [
                Cocoon(
                    id="root-cocoon",
                    name="Root",
                    owner_user_id="owner-1",
                    character_id="character-1",
                    selected_model_id="model-1",
                ),
                Cocoon(
                    id="child-cocoon",
                    name="Child",
                    owner_user_id="owner-1",
                    character_id="character-1",
                    selected_model_id="model-1",
                    parent_id="root-cocoon",
                ),
                Message(
                    id="parent-message",
                    cocoon_id="root-cocoon",
                    role="user",
                    content="from parent",
                    created_at=base_time + timedelta(seconds=1),
                    updated_at=base_time + timedelta(seconds=1),
                ),
                Message(
                    id="child-message",
                    cocoon_id="child-cocoon",
                    role="assistant",
                    content="from child",
                    created_at=base_time + timedelta(seconds=2),
                    updated_at=base_time + timedelta(seconds=2),
                ),
            ]
        )
        session.commit()

        visible = service.list_visible_messages(
            session,
            10,
            [],
            cocoon_id="child-cocoon",
        )

        assert [message.id for message in visible] == ["parent-message", "child-message"]
