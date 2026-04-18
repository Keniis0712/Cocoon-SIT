# ConnectionManager

源码：`backend/app/services/realtime/connection_manager.py`

## 功能

- 管理当前进程内每个 cocoon 的 WebSocket 连接集合。
- 负责本地广播以及断链清理。

## 对外接口

- `bind_loop(loop)`
- `connect(cocoon_id, websocket)`
- `disconnect(cocoon_id, websocket)`
- `broadcast_local(cocoon_id, event)`

## 交互方式

- `cocoon_ws` 路由负责接入和断开。
- `EventDeliveryService` 或 `RealtimeHub` 会驱动本地广播。
