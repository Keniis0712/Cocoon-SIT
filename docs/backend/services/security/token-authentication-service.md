# TokenAuthenticationService

源码：`backend/app/services/security/token_authentication_service.py`

## 功能

- 把 token 解析结果映射成活跃用户。
- 同时提供 websocket 场景的异常转换，以及权限检查辅助。

## 对外接口

- `resolve_active_user(session, token)`
- `resolve_active_websocket_user(session, token)`
- `require_user_permission(session, user, permission)`

## 交互方式

- `api/deps.py` 的 REST / WebSocket 鉴权都通过它走。
- 依赖 `TokenService` 和 `rbac.require_permission()`。
