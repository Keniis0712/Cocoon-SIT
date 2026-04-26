from __future__ import annotations

from sqlalchemy import select

from app.core.config import Settings
from app.models import ActionDispatch, AvailableModel, Character, ChatGroupRoom, Cocoon, Message, ModelProvider, User
from app.services.catalog.system_settings_service import SystemSettingsService
from app.services.workspace.message_dispatch_service import MessageDispatchService
from tests.sqlite_helpers import make_sqlite_session_factory


class _Queue:
    def __init__(self) -> None:
        self.enqueued: list[dict] = []

    def enqueue(
        self,
        action_id: str,
        *,
        event_type: str,
        cocoon_id: str | None = None,
        chat_group_id: str | None = None,
        payload: dict,
    ) -> int:
        self.enqueued.append(
            {
                "action_id": action_id,
                "event_type": event_type,
                "cocoon_id": cocoon_id,
                "chat_group_id": chat_group_id,
                "payload": payload,
            }
        )
        return len(self.enqueued)


class _Hub:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def publish(self, channel_key: str, payload: dict) -> None:
        self.events.append((channel_key, payload))


def _session_factory():
    return make_sqlite_session_factory()


def _seed_conversation(session):
    user = User(username="owner", email="owner@example.com", password_hash="x")
    provider = ModelProvider(name="provider", kind="mock", capabilities_json={})
    session.add_all([user, provider])
    session.flush()

    model = AvailableModel(provider_id=provider.id, model_name="test-model")
    character = Character(
        name="Character",
        prompt_summary="Prompt",
        created_by_user_id=user.id,
    )
    session.add_all([model, character])
    session.flush()

    cocoon = Cocoon(
        name="Workspace",
        owner_user_id=user.id,
        character_id=character.id,
        selected_model_id=model.id,
    )
    room = ChatGroupRoom(
        name="Room",
        owner_user_id=user.id,
        character_id=character.id,
        selected_model_id=model.id,
    )
    session.add_all([cocoon, room])
    session.commit()
    return cocoon.id, room.id


def test_message_dispatch_service_aggregates_private_messages_into_pending_action():
    session_factory = _session_factory()
    queue = _Queue()
    hub = _Hub()
    service = MessageDispatchService(
        chat_queue=queue,
        realtime_hub=hub,
        system_settings_service=SystemSettingsService(Settings()),
    )

    with session_factory() as session:
        cocoon_id, _ = _seed_conversation(session)
        settings = service.system_settings_service.get_settings(session)
        settings.private_chat_debounce_seconds = 5
        session.commit()

        first = service.enqueue_chat_message(
            session,
            cocoon_id,
            content="first",
            client_request_id="private-1",
            timezone="UTC",
        )

    with session_factory() as session:
        second = service.enqueue_chat_message(
            session,
            cocoon_id,
            content="second",
            client_request_id="private-2",
            timezone="UTC",
        )
        assert second.id == first.id
        action = session.get(ActionDispatch, first.id)
        messages = list(session.scalars(select(Message).where(Message.action_id == first.id)).all())
        assert action is not None
        assert action.payload_json["aggregated_message_count"] == 2
        assert len(messages) == 2

    assert len(queue.enqueued) == 1
    assert len(hub.events) == 1


def test_message_dispatch_service_aggregates_group_messages_into_pending_action():
    session_factory = _session_factory()
    queue = _Queue()
    hub = _Hub()
    service = MessageDispatchService(
        chat_queue=queue,
        realtime_hub=hub,
        system_settings_service=SystemSettingsService(Settings()),
    )

    with session_factory() as session:
        _, room_id = _seed_conversation(session)
        settings = service.system_settings_service.get_settings(session)
        settings.group_chat_debounce_seconds = 5
        session.commit()

        first = service.enqueue_chat_group_message(
            session,
            room_id,
            content="first",
            client_request_id="group-1",
            timezone="UTC",
            sender_user_id=None,
            external_sender_id="im-1",
            external_sender_display_name="Alice",
        )

    with session_factory() as session:
        second = service.enqueue_chat_group_message(
            session,
            room_id,
            content="second",
            client_request_id="group-2",
            timezone="UTC",
            sender_user_id=None,
            external_sender_id="im-2",
            external_sender_display_name="Bob",
        )
        assert second.id == first.id
        action = session.get(ActionDispatch, first.id)
        messages = list(session.scalars(select(Message).where(Message.action_id == first.id)).all())
        assert action is not None
        assert action.payload_json["aggregated_message_count"] == 2
        assert action.payload_json["external_sender_id"] == "im-2"
        assert len(messages) == 2

    assert len(queue.enqueued) == 1
    assert len(hub.events) == 1
