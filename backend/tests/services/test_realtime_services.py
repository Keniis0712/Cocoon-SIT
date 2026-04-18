from app.services.realtime.connection_manager import ConnectionManager
from app.services.realtime.event_delivery_service import EventDeliveryService
from app.services.realtime.hub import RealtimeHub


class _DummyWebSocket:
    def __init__(self) -> None:
        self.accepted = False
        self.payloads: list[dict] = []

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, payload: dict) -> None:
        self.payloads.append(payload)


class _RecordingBackplane:
    def __init__(self) -> None:
        self.published: list[tuple[str, dict]] = []
        self.handlers = []
        self.started = False
        self.stopped = False

    def publish(self, cocoon_id: str, event: dict) -> None:
        self.published.append((cocoon_id, event))

    def subscribe(self, handler) -> None:
        self.handlers.append(handler)

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True


class _RecordingDeliveryService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def deliver(self, manager: ConnectionManager, cocoon_id: str, event: dict) -> None:
        self.calls.append((cocoon_id, event))


def test_connection_manager_tracks_and_cleans_up_connections():
    import asyncio

    manager = ConnectionManager()
    websocket = _DummyWebSocket()

    asyncio.run(manager.connect("cocoon-1", websocket))
    assert websocket.accepted is True
    assert websocket in manager.connections["cocoon-1"]

    manager.disconnect("cocoon-1", websocket)
    assert "cocoon-1" not in manager.connections


def test_event_delivery_service_broadcasts_without_bound_loop():
    import asyncio

    manager = ConnectionManager()
    websocket = _DummyWebSocket()
    asyncio.run(manager.connect("cocoon-1", websocket))

    service = EventDeliveryService()
    service.deliver(manager, "cocoon-1", {"type": "ping"})

    assert websocket.payloads == [{"type": "ping"}]


def test_realtime_hub_delegates_publish_and_delivery():
    backplane = _RecordingBackplane()
    manager = ConnectionManager()
    delivery_service = _RecordingDeliveryService()
    hub = RealtimeHub(manager, backplane, delivery_service=delivery_service)

    hub.start()
    hub.publish("cocoon-1", {"type": "queued"})
    hub.handle_backplane_event("cocoon-1", {"type": "reply_done"})
    hub.stop()

    assert backplane.started is True
    assert backplane.stopped is True
    assert backplane.published == [("cocoon-1", {"type": "queued"})]
    assert delivery_service.calls == [("cocoon-1", {"type": "reply_done"})]
