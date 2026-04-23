from app.services.plugins.external_sdk import ExternalEventContext
from app.services.plugins.im_sdk import ImPluginContext


class _Queue:
    def __init__(self):
        self.items = []

    def put(self, item):
        self.items.append(item)


def test_external_event_context_emits_events_and_heartbeats():
    queue = _Queue()
    context = ExternalEventContext(
        plugin_name="plugin",
        plugin_version="1.0.0",
        event_name="tick",
        plugin_config={"x": 1},
        event_config={"y": 2},
        data_dir="data/plugin",
        outbound_queue=queue,
    )

    context.emit_event({"target_type": "cocoon"})
    context.heartbeat()
    context.report_user_error("user-1", "bad key")
    context.clear_user_error("user-1")

    assert queue.items[0] == {
        "type": "external_event",
        "plugin_event": "tick",
        "envelope": {"target_type": "cocoon"},
    }
    assert queue.items[1]["type"] == "heartbeat"
    assert queue.items[1]["plugin_event"] == "tick"
    assert "occurred_at" in queue.items[1]
    assert queue.items[2]["type"] == "user_error"
    assert queue.items[2]["user_id"] == "user-1"
    assert queue.items[3]["type"] == "user_error_clear"
    assert queue.items[3]["user_id"] == "user-1"


def test_sdk_contexts_noop_without_outbound_queue():
    external = ExternalEventContext(
        plugin_name="plugin",
        plugin_version="1.0.0",
        event_name="tick",
        plugin_config={},
        event_config={},
        data_dir="data/plugin",
        outbound_queue=None,
    )
    im = ImPluginContext(
        plugin_name="plugin",
        plugin_version="1.0.0",
        plugin_config={},
        data_dir="data/plugin",
        outbound_queue=None,
    )

    external.emit_event({"ignored": True})
    external.heartbeat()
    im.heartbeat()


def test_im_plugin_context_emits_heartbeat():
    queue = _Queue()
    context = ImPluginContext(
        plugin_name="plugin",
        plugin_version="1.0.0",
        plugin_config={"x": 1},
        data_dir="data/plugin",
        outbound_queue=queue,
    )

    context.heartbeat()
    context.report_user_error("user-2", "invalid location")
    context.clear_user_error("user-2")

    assert queue.items[0]["type"] == "heartbeat"
    assert "occurred_at" in queue.items[0]
    assert queue.items[1]["type"] == "user_error"
    assert queue.items[1]["user_id"] == "user-2"
    assert queue.items[2]["type"] == "user_error_clear"
    assert queue.items[2]["user_id"] == "user-2"
