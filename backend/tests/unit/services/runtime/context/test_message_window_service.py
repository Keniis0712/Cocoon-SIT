from datetime import UTC, datetime, timedelta

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
