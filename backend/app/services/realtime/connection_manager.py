"""In-process websocket connection tracking."""

from __future__ import annotations

import asyncio
from collections import defaultdict

from fastapi import WebSocket


class ConnectionManager:
    """Tracks active websocket connections per cocoon inside one process."""

    def __init__(self) -> None:
        self.connections: dict[str, set[WebSocket]] = defaultdict(set)
        self.loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Bind the running event loop used for cross-thread delivery."""
        self.loop = loop

    async def connect(self, cocoon_id: str, websocket: WebSocket) -> None:
        """Accept and register a websocket for the target cocoon."""
        await websocket.accept()
        self.connections[cocoon_id].add(websocket)

    def disconnect(self, cocoon_id: str, websocket: WebSocket) -> None:
        """Remove a websocket from the cocoon connection registry."""
        self.connections[cocoon_id].discard(websocket)
        if not self.connections[cocoon_id]:
            self.connections.pop(cocoon_id, None)

    async def broadcast_local(self, cocoon_id: str, event: dict) -> None:
        """Broadcast an event to every local websocket subscribed to a cocoon."""
        stale: list[WebSocket] = []
        for websocket in list(self.connections.get(cocoon_id, set())):
            try:
                await websocket.send_json(event)
            except Exception:
                stale.append(websocket)
        for websocket in stale:
            self.disconnect(cocoon_id, websocket)
