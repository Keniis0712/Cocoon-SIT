# WorkspaceRealtimeService

源码：`backend/app/services/workspace/workspace_realtime_service.py`

## 功能

- 封装 cocoon websocket 的鉴权、权限检查、存在性校验和连接管理。
- 把 websocket 接入逻辑从 router 中抽离成可复用服务。

## 对外接口

- `connect_authenticated(websocket, cocoon_id, permission)`
- `disconnect(cocoon_id, websocket)`

## 交互方式

- 上游由 `workspace/realtime.py` 调用。
- 下游依赖 `TokenAuthenticationService`、`ConnectionManager` 和数据库会话。

## 注意点

- 支持 `access_token` query 参数或 `Authorization: Bearer ...`。
