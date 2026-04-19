"""In-process websocket connection tracking."""

from __future__ import annotations

import asyncio
from collections import defaultdict

from fastapi import WebSocket


class ConnectionManager:
    """Tracks active websocket connections per realtime channel inside one process."""

    def __init__(self) -> None:
        self.connections: dict[str, set[WebSocket]] = defaultdict(set)
        self.loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Bind the running event loop used for cross-thread delivery."""
        self.loop = loop

    async def connect(self, channel_key: str, websocket: WebSocket) -> None:
        """Accept and register a websocket for the target channel."""
        await websocket.accept()
        self.connections[channel_key].add(websocket)

    def disconnect(self, channel_key: str, websocket: WebSocket) -> None:
        """Remove a websocket from the channel connection registry."""
        self.connections[channel_key].discard(websocket)
        if not self.connections[channel_key]:
            self.connections.pop(channel_key, None)

    async def broadcast_local(self, channel_key: str, event: dict) -> None:
        """Broadcast an event to every local websocket subscribed to a channel."""
        stale: list[WebSocket] = []
        for websocket in list(self.connections.get(channel_key, set())):
            try:
                await websocket.send_json(event)
            except Exception:
                stale.append(websocket)
        for websocket in stale:
            self.disconnect(channel_key, websocket)
