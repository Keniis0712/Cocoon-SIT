from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, WebSocketException


router = APIRouter()


@router.websocket("/{cocoon_id}/ws")
async def cocoon_ws(websocket: WebSocket, cocoon_id: str) -> None:
    container = websocket.app.state.container
    try:
        await container.workspace_realtime_service.connect_authenticated(
            websocket,
            cocoon_id,
            "cocoons:read",
            target_type="cocoon",
        )
    except WebSocketException as exc:
        await websocket.close(code=exc.code)
        return
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        container.workspace_realtime_service.disconnect(cocoon_id, websocket, target_type="cocoon")
