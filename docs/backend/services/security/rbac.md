# RBAC Helpers

源码：`backend/app/services/security/rbac.py`

## 功能

- 计算用户的有效权限集合。
- 在 API 层做基于权限字符串的快速拦截。

## 对外接口

- `list_permissions_for_user(session, user)`
- `require_permission(session, user, permission)`

## 交互方式

- 几乎所有受保护路由都会通过 `api/deps.py` 间接调用这里。
- WebSocket 鉴权也依赖同一套权限检查。
