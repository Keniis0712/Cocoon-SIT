"""Backplane-backed realtime hub."""

from __future__ import annotations

from app.services.realtime.backplane import RealtimeBackplane
from app.services.realtime.connection_manager import ConnectionManager
from app.services.realtime.event_delivery_service import EventDeliveryService


class RealtimeHub:
    """Bridges published events from the backplane into local websocket delivery."""

    def __init__(
        self,
        manager: ConnectionManager,
        backplane: RealtimeBackplane,
        delivery_service: EventDeliveryService | None = None,
    ):
        self.manager = manager
        self.backplane = backplane
        self.delivery_service = delivery_service or EventDeliveryService()
        self.backplane.subscribe(self.handle_backplane_event)

    def start(self) -> None:
        """Start the backplane listener."""
        self.backplane.start()

    def stop(self) -> None:
        """Stop the backplane listener."""
        self.backplane.stop()

    def publish(self, cocoon_id: str, event: dict) -> None:
        """Publish an event into the configured backplane."""
        self.backplane.publish(cocoon_id, event)

    def handle_backplane_event(self, cocoon_id: str, event: dict) -> None:
        """Forward a backplane event into local websocket delivery."""
        self.delivery_service.deliver(self.manager, cocoon_id, event)
