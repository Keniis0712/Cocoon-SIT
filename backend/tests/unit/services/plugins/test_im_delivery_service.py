from types import SimpleNamespace

from sqlalchemy import select

from app.models import PluginImDeliveryOutbox, PluginImTargetRoute
from app.services.plugins.im_delivery_service import PLUGIN_IM_SOURCE_KIND, PluginImDeliveryService
from tests.sqlite_helpers import make_sqlite_session_factory


class _Session:
    def __init__(self):
        self.added = []

    def add(self, item):
        self.added.append(item)

    def flush(self):
        return None


def test_im_delivery_service_enqueues_only_for_im_origin_actions():
    service = PluginImDeliveryService()
    session = _Session()
    message = SimpleNamespace(id="message-1", content="hello world")

    plain_action = SimpleNamespace(
        id="action-1",
        cocoon_id="cocoon-1",
        chat_group_id=None,
        event_type="chat",
        payload_json={},
    )
    assert service.enqueue_reply(session, action=plain_action, message=message) is None
    assert session.added == []

    im_action = SimpleNamespace(
        id="action-2",
        cocoon_id="cocoon-1",
        chat_group_id=None,
        event_type="chat",
        payload_json={
            "source_kind": PLUGIN_IM_SOURCE_KIND,
            "source_plugin_id": "plugin-1",
            "message_id": "source-message-1",
            "external_account_id": "acct-1",
            "external_conversation_id": "conv-1",
            "external_message_id": "ext-msg-1",
        },
    )
    outbox = service.enqueue_reply(session, action=im_action, message=message)

    assert outbox is not None
    assert outbox.plugin_id == "plugin-1"
    assert outbox.payload_json["reply_text"] == "hello world"
    assert outbox.payload_json["external_message_id"] == "ext-msg-1"
    assert len(session.added) == 1


def test_im_delivery_service_fans_out_wakeup_reply_to_all_registered_routes():
    session_factory = make_sqlite_session_factory()
    service = PluginImDeliveryService()
    action = SimpleNamespace(
        id="action-wakeup-1",
        cocoon_id="cocoon-1",
        chat_group_id=None,
        event_type="wakeup",
        payload_json={},
    )
    message = SimpleNamespace(id="message-1", content="wake up reply")

    with session_factory() as session:
        session.add(
            PluginImTargetRoute(
                plugin_id="plugin-1",
                target_type="cocoon",
                target_id="cocoon-1",
                external_platform="onebot_v11",
                conversation_kind="private",
                external_account_id="acct-1",
                external_conversation_id="conv-1",
                route_metadata_json={"conversation_kind": "private"},
            )
        )
        session.add(
            PluginImTargetRoute(
                plugin_id="plugin-2",
                target_type="cocoon",
                target_id="cocoon-1",
                external_platform="discord",
                conversation_kind="group",
                external_account_id="acct-2",
                external_conversation_id="conv-2",
                route_metadata_json={"conversation_kind": "group"},
            )
        )
        session.flush()

        first_outbox = service.enqueue_reply(session, action=action, message=message)
        rows = list(session.scalars(select(PluginImDeliveryOutbox).order_by(PluginImDeliveryOutbox.created_at.asc())).all())

    assert first_outbox is not None
    assert len(rows) == 2
    assert {row.plugin_id for row in rows} == {"plugin-1", "plugin-2"}
    assert {row.payload_json["external_conversation_id"] for row in rows} == {"conv-1", "conv-2"}
    assert {row.payload_json["metadata_json"]["conversation_kind"] for row in rows} == {"private", "group"}
