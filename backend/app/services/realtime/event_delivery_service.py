"""Loop-aware event delivery helper for realtime broadcasts."""

from __future__ import annotations

import asyncio

from app.services.realtime.connection_manager import ConnectionManager


class EventDeliveryService:
    """Schedules local websocket delivery on the appropriate asyncio loop."""

    def deliver(self, manager: ConnectionManager, cocoon_id: str, event: dict) -> None:
        """Deliver a cocoon event through the manager on the available loop."""
        if manager.loop and manager.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                manager.broadcast_local(cocoon_id, event),
                manager.loop,
            )
            return
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(manager.broadcast_local(cocoon_id, event))
        except RuntimeError:
            asyncio.run(manager.broadcast_local(cocoon_id, event))
