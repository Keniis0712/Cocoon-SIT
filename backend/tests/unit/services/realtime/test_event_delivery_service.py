import asyncio
from types import SimpleNamespace

from app.services.realtime.event_delivery_service import EventDeliveryService


def test_deliver_uses_manager_loop_when_running(monkeypatch):
    recorded = {}

    async def broadcast_local(cocoon_id, event):
        recorded["broadcast_args"] = (cocoon_id, event)

    def fake_run_coroutine_threadsafe(coro, loop):
        recorded["loop"] = loop
        original_run(coro)
        return "future"

    original_run = asyncio.run
    monkeypatch.setattr(
        "app.services.realtime.event_delivery_service.asyncio.run_coroutine_threadsafe",
        fake_run_coroutine_threadsafe,
    )

    manager = SimpleNamespace(
        loop=SimpleNamespace(is_running=lambda: True),
        broadcast_local=broadcast_local,
    )

    EventDeliveryService().deliver(manager, "cocoon-1", {"type": "ping"})

    assert recorded["loop"] is manager.loop
    assert recorded["broadcast_args"] == ("cocoon-1", {"type": "ping"})


def test_deliver_creates_task_on_current_loop(monkeypatch):
    recorded = {}

    async def broadcast_local(cocoon_id, event):
        recorded["broadcast_args"] = (cocoon_id, event)

    class _FakeLoop:
        def create_task(self, coro):
            recorded["task_created"] = True
            original_run(coro)
            return "task"

    original_run = asyncio.run
    monkeypatch.setattr(
        "app.services.realtime.event_delivery_service.asyncio.get_running_loop",
        lambda: _FakeLoop(),
    )

    manager = SimpleNamespace(loop=None, broadcast_local=broadcast_local)

    EventDeliveryService().deliver(manager, "group-1", {"type": "reply"})

    assert recorded["task_created"] is True
    assert recorded["broadcast_args"] == ("group-1", {"type": "reply"})


def test_deliver_falls_back_to_asyncio_run_when_no_loop(monkeypatch):
    recorded = {}
    original_run = asyncio.run

    async def broadcast_local(cocoon_id, event):
        recorded["broadcast_args"] = (cocoon_id, event)

    def fake_run(coro):
        recorded["ran"] = True
        return original_run(coro)

    monkeypatch.setattr(
        "app.services.realtime.event_delivery_service.asyncio.get_running_loop",
        lambda: (_ for _ in ()).throw(RuntimeError("no loop")),
    )
    monkeypatch.setattr("app.services.realtime.event_delivery_service.asyncio.run", fake_run)

    manager = SimpleNamespace(loop=None, broadcast_local=broadcast_local)

    EventDeliveryService().deliver(manager, "cocoon-2", {"type": "done"})

    assert recorded["ran"] is True
    assert recorded["broadcast_args"] == ("cocoon-2", {"type": "done"})
